using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace CosmonSWService
{
    /// <summary>
    /// Parallel implementation of model state retrieval.
    /// 
    /// Strategy:
    /// 1. Get first feature ID via single COM call (doc.FirstFeature)
    /// 2. Get ALL features via GetFeatures(false) - single COM call
    /// 3. Extract ALL properties AND relationships in PARALLEL:
    ///    - Properties: Name, Type, Suppressed, RolledBack, IsInternal, IsFolder
    ///    - Relationships: NextFeatureId, FirstSubFeatureId, NextSubFeatureId, OwnerId
    /// 4. Reconstruct tree using pre-extracted relationships with ZERO additional COM calls
    ///    (folder contents determined by pre-extracted OwnerFolder, not runtime GetFeatures())
    /// 
    /// This achieves true parallelization: expensive COM property/relationship extraction
    /// happens in parallel, then tree reconstruction is pure in-memory operations.
    /// </summary>
    public class ParallelModelStateManager
    {
        private readonly Func<SolidWorksConnection> _getConnection;

        // When true, inject a synthetic cycle into the extracted feature data before
        // tree reconstruction.  Used for testing that cycle detection still works after
        // the folder ordering fix removed natural cycle sources.
        // Set COSMON_INJECT_CYCLE=1 before starting the C# service to enable.
        private static readonly bool InjectCycleForTesting =
            System.Environment.GetEnvironmentVariable("COSMON_INJECT_CYCLE") == "1";

        // Profiling: Track session statistics for timing analysis
        private static readonly SessionStats _sessionStats = new SessionStats();

        // Documents and Feature objects from the most recent top-level walk (the root
        // document plus every subpart it descended into) kept alive so the next walk's
        // GetFeatures(false) hands back the same RCWs instead of re-acquiring each wrapper
        // through COM. A HashSet dedupes by reference (a part instanced many times is held
        // once). Replaced wholesale at the end of each top-level GetModelState call, so it
        // holds exactly one walk's references and never grows unboundedly.
        private static WalkPreservation _preserved = new WalkPreservation();

        // Maximum degree of parallelism (4 threads observed as optimal, but never exceed CPU cores)
        private static readonly int MAX_PARALLELISM = Math.Min(4, System.Environment.ProcessorCount);

        // Assembly subpart descent: cap on the number of UNIQUE referenced documents
        // expanded per GetModelState call (duplicate instances do not count toward it),
        // and a recursion-depth guard for nested sub-assemblies.
        private const int MAX_SUBPARTS = 20;
        private const int MAX_DEPTH = 5;

        public ParallelModelStateManager(Func<SolidWorksConnection> getConnection)
        {
            _getConnection = getConnection ?? throw new ArgumentNullException(nameof(getConnection));
        }

        /// <summary>
        /// Get the current model state using parallel feature property extraction.
        /// </summary>
        /// <exception cref="InvalidOperationException">Thrown when not connected to SolidWorks or no document is open.</exception>
        public Dictionary<string, object> GetModelState()
        {
            var prof = new SimpleProfiler("GetModelStateParallel");

            if (!_getConnection().IsConnected)
                throw new InvalidOperationException("Not connected to SolidWorks");

            ISldWorks swApp = _getConnection().SwApp;
            ModelDoc2 doc = swApp.ActiveDoc as ModelDoc2;

            if (doc == null)
            {
                throw new InvalidOperationException("No active document is open in SolidWorks");
            }

            string docTitle = doc.GetTitle();
            int runNumber = _sessionStats.WalkCount + 1;
            prof.Mark($"doc='{docTitle}', run={runNumber}");

            var ctx = new WalkContext { RunNumber = runNumber };
            var walkSw = Stopwatch.StartNew();

            // Use performance optimization scope to disable UI updates during extraction.
            // After parallel property extraction, error info is fetched via a single bulk
            // GetWhatsWrong() call and distributed into the extracted feature data.
            Dictionary<string, object> modelState;
            int errorCount, warningCount;
            List<Dictionary<string, object>> featureErrors;
            List<string> rawErrorMessages;
            using (new PerformanceOptimizationScope(swApp, doc))
            {
                // GetErrorMessages is a drain-on-read, application-wide buffer that can hold
                // stale/cross-document entries — drain it so the post-rebuild read below
                // reflects only THIS document's rebuild.
                DrainErrorMessages(swApp);

                // Refresh the model so the walk sees the post-rebuild feature tree
                // (suppression flags, error states, rolled-back markers all settle on rebuild).
                // EditRebuild3 only touches features that need it, so this is cheap when nothing changed.
                doc.EditRebuild3();

                // Capture the rich "What's Wrong" report text now, before the tree walk's
                // selections push their own "Selection Failed" entries into the shared buffer.
                rawErrorMessages = CaptureErrorMessages(swApp);

                // WalkDocument extracts this document's own tree and, for an assembly,
                // descends into each component to attach its subpart tree.
                modelState = WalkDocument(doc, isRoot: true, depth: 0, ctx,
                    out errorCount, out warningCount, out featureErrors);

                // Top-level document state. Recorded once for the active root document only
                // (not per nested subpart — these are properties of the open editing session,
                // not of every referenced file). Both are pure reads that leave the view
                // untouched.
                modelState["document_orientation"] = GetDocumentUpAxis(doc);
                modelState["sketch_mode_active"] = IsSketchModeActive(doc);
            }

            // Hold this walk's RCWs alive (replacing the previous walk's) for reuse next time.
            _preserved = ctx.Preserve;
            Console.WriteLine($"[PROFILE] Preserved {_preserved.Features.Count} features, " +
                $"{_preserved.Docs.Count} docs for RCW reuse");

            // Add document-level fields (computed outside tree reconstruction)
            modelState["error_count"] = errorCount;
            modelState["warning_count"] = warningCount;
            modelState["feature_errors"] = featureErrors;
            modelState["raw_error_messages"] = rawErrorMessages;

            walkSw.Stop();

            _sessionStats.RecordWalk(walkSw.ElapsedMilliseconds);

            prof.Done($"walk_complete: {walkSw.ElapsedMilliseconds}ms");
            _sessionStats.LogSummary();

            return modelState;
        }

        /// <summary>
        /// Get the model state for a single named component's referenced document instead
        /// of the active assembly's own tree. <paramref name="subcomponentName"/> is the
        /// component instance name (IComponent2.Name2) as shown on the assembly's
        /// [Reference] nodes. The component's document is walked the same way as a subpart,
        /// so a sub-assembly target descends into its children under the same
        /// MAX_SUBPARTS / MAX_DEPTH caps, rooted at it.
        /// </summary>
        /// Precondition failures (not connected, no document, the active document is not an
        /// assembly, the component is missing, or it cannot be resolved) are returned as
        /// reported-error results so they surface to the agent as a correctable message
        /// rather than an internal error.
        public Dictionary<string, object> GetModelState(string subcomponentName)
        {
            if (string.IsNullOrEmpty(subcomponentName))
                return GetModelState();

            if (!_getConnection().IsConnected)
                return Protocol.ReportedErrorResult("Not connected to SolidWorks");

            ISldWorks swApp = _getConnection().SwApp;
            ModelDoc2 doc = swApp.ActiveDoc as ModelDoc2;
            if (doc == null)
                return Protocol.ReportedErrorResult("No active document is open in SolidWorks");

            AssemblyDoc asm = doc as AssemblyDoc;
            if (asm == null)
                return Protocol.ReportedErrorResult(
                    "The active document is not an assembly; the 'subcomponent' option applies "
                    + "only to assembly components");

            IComponent2 comp = FindComponentByName(asm, subcomponentName);
            if (comp == null)
                return Protocol.ReportedErrorResult(
                    "No component named '" + subcomponentName + "' in the active assembly");

            ModelDoc2 sub = comp.GetModelDoc2() as ModelDoc2;
            if (sub == null)
                return Protocol.ReportedErrorResult(
                    "Component '" + subcomponentName + "' is suppressed, lightweight, or unloaded "
                    + "and cannot be expanded");

            var ctx = new WalkContext { RunNumber = _sessionStats.WalkCount + 1 };
            Dictionary<string, object> tree;
            using (new PerformanceOptimizationScope(swApp, doc))
            {
                // Walk the chosen component as the response root (isRoot: false — no rebuild
                // or error pass), descending into it if it is itself a sub-assembly.
                tree = WalkDocument(sub, isRoot: false, depth: 0, ctx, out _, out _, out _);
            }
            _preserved = ctx.Preserve;

            // Shape the walked tree as a standard model-state response so the agent-side
            // parser handles it unchanged (document_title/document_path/feature_count/features
            // come from WalkDocument). This non-root walk skips the per-feature error pass,
            // so the error/warning fields are empty.
            tree["error_count"] = 0;
            tree["warning_count"] = 0;
            tree["feature_errors"] = new List<Dictionary<string, object>>();
            tree["raw_error_messages"] = new List<string>();
            return tree;
        }

        /// <summary>
        /// Find a component in the assembly whose instance name (Name2) matches exactly.
        /// Searches all components (top-level and nested); returns null when none match.
        /// </summary>
        private static IComponent2 FindComponentByName(AssemblyDoc asm, string name)
        {
            object[] comps = asm.GetComponents(false) as object[];
            if (comps == null)
                return null;

            foreach (object o in comps)
            {
                IComponent2 comp = o as IComponent2;
                if (comp != null && comp.Name2 == name)
                    return comp;
            }
            return null;
        }

        /// <summary>
        /// Determines the document's up axis ("Y_up", "Z_up", "X_up", or "unknown") from the
        /// Top standard view's orientation matrix, read via GetStandardViewRotation.
        ///
        /// GetStandardViewRotation is a pure getter: it returns the rotation that
        /// ShowNamedView2 would apply for the same view id, but without touching the active
        /// view — so there is no view change to undo, no animation-speed preference to clear,
        /// and no flicker, unlike showing the view and reading Orientation3 back. The Top view
        /// is selected by its swStandardViews_e id, which is language-independent; the "*Top"
        /// view-name string is locale-sensitive and silently fails to resolve on non-English
        /// installs. The returned 9-double array is the col-major 3x3 view rotation; row 2
        /// (elements [2], [5], [8]) is the camera direction = the Top plane normal in world
        /// coords = the document up axis. SolidWorks defines the standard views relative to the
        /// Front view, so a user-redefined Front is reflected here exactly as it would be when
        /// showing the view.
        /// </summary>
        private static string GetDocumentUpAxis(ModelDoc2 doc)
        {
            double[] orientation =
                doc.GetStandardViewRotation((int)swStandardViews_e.swTopView) as double[];
            if (orientation == null || orientation.Length < 9)
                return "unknown";

            double upX = Math.Abs(orientation[2]);
            double upY = Math.Abs(orientation[5]);
            double upZ = Math.Abs(orientation[8]);

            if (upY > 0.9)
                return "Y_up";
            if (upZ > 0.9)
                return "Z_up";
            if (upX > 0.9)
                return "X_up";
            return "unknown";
        }

        /// <summary>
        /// Returns true when a sketch is currently open for editing (the document is "in sketch
        /// mode"). ISketchManager.ActiveSketch is non-null only while a sketch is being edited,
        /// and null otherwise.
        /// </summary>
        private static bool IsSketchModeActive(ModelDoc2 doc)
        {
            SketchManager sketchMgr = doc.SketchManager;
            if (sketchMgr == null)
                return false;
            return sketchMgr.ActiveSketch != null;
        }

        /// <summary>
        /// Documents and Feature RCWs kept alive from one top-level walk so the next walk's
        /// GetFeatures(false) reuses the same wrappers instead of re-acquiring them. Deduped
        /// by reference (a part instanced many times is held once).
        /// </summary>
        private sealed class WalkPreservation
        {
            public readonly HashSet<ModelDoc2> Docs = new HashSet<ModelDoc2>();
            public readonly HashSet<Feature> Features = new HashSet<Feature>();
        }

        /// <summary>
        /// State threaded through one top-level walk and its recursive component descents:
        /// the profiling run number, the alive-RCW set being built for this walk, and the
        /// per-document dedup map ("path::config" -> authoritative GetTitle recorded at first
        /// expansion) that also serves as the unique-document budget for MAX_SUBPARTS.
        /// </summary>
        private sealed class WalkContext
        {
            public int RunNumber;
            public readonly WalkPreservation Preserve = new WalkPreservation();
            public readonly Dictionary<string, string> Seen = new Dictionary<string, string>();
        }

        /// <summary>
        /// Internal data structure to hold extracted feature properties AND relationships.
        /// All relationships are stored as Feature references (not IDs) for zero COM calls during reconstruction.
        /// Using object references eliminates GetID() calls - same RCW is returned each time.
        /// </summary>
        private class FeatureData
        {
            // The feature itself (used as dictionary key and for folder processing)
            public Feature FeatureRef;

            // Properties
            public string Name;
            public string Type;
            public bool Suppressed;
            public bool RolledBack;
            public bool IsInternal;
            public bool IsFolder;

            // Relationships (stored as Feature references - same RCW returned each time, no GetID needed)
            public Feature NextFeature;       // GetNextFeature() - next in flat list
            public Feature FirstSubFeature;   // GetFirstSubFeature() - first child
            public Feature NextSubFeature;    // GetNextSubFeature() - next sibling (for sub-features)
            public Feature Owner;             // GetOwnerFeature() - parent (null = top-level)
            public Feature OwnerFolder;       // FeatureFolderLocation() - containing folder (null = not in a folder)

            // For copy detection (Feature references, not IDs)
            public Feature[] Parents;         // GetParents() - array of parent features

            /// <summary>
            /// Convert to the dictionary format used in the JSON response.
            /// </summary>
            public Dictionary<string, object> ToDict()
            {
                return new Dictionary<string, object>
                {
                    ["is_copy"] = false,
                    ["name"] = Name,
                    ["type"] = Type,
                    ["suppressed"] = Suppressed,
                    ["rolled_back"] = RolledBack
                };
            }
        }

        /// <summary>
        /// Walk a single document into a model-state tree (always parallel extraction). For
        /// an assembly, also descends into each component and attaches its subpart tree to the
        /// matching node in this document's own feature list.
        ///
        /// <paramref name="isRoot"/> marks the active document the request was made for: only
        /// the root runs the per-feature error pass (GetWhatsWrong), the verbose profiling, and
        /// the test cycle injection. Subpart walks (isRoot false) skip all three and report no
        /// errors. <paramref name="ctx"/> carries the run number, the alive-RCW set being built,
        /// and the dedup/budget map shared across the whole walk.
        /// </summary>
        private Dictionary<string, object> WalkDocument(
            ModelDoc2 doc, bool isRoot, int depth, WalkContext ctx,
            out int errorCount, out int warningCount,
            out List<Dictionary<string, object>> featureErrors)
        {
            errorCount = 0;
            warningCount = 0;
            featureErrors = new List<Dictionary<string, object>>();
            int runNumber = ctx.RunNumber;
            SimpleProfiler prof = isRoot
                ? new SimpleProfiler($"WalkDocument(run={runNumber})")
                : null;
            var timers = new NamedTimers();

            // Keep this document's RCW alive for reuse on the next walk.
            ctx.Preserve.Docs.Add(doc);

            string documentTitle = doc.GetTitle();
            // Full path of the active document; empty string for an unsaved document.
            // Emitted as "document_path" so the agent can key per-document model
            // state and never diff one document's feature tree against another's.
            string documentPath = doc.GetPathName();
            prof?.Mark("got_doc");

            // Step 1: Get first feature (no GetID call needed - we use object references)
            var sw = Stopwatch.StartNew();
            Feature firstFeature = doc.FirstFeature() as Feature;
            sw.Stop();
            timers.AddTicks("GetFirstFeature", sw.ElapsedTicks);

            if (firstFeature == null)
            {
                prof?.Mark("no_features");
                return new Dictionary<string, object>
                {
                    ["document_title"] = documentTitle,
                    ["document_path"] = documentPath,
                    ["feature_count"] = 0,
                    ["features"] = new List<Dictionary<string, object>>()
                };
            }

            // Step 2: Get ALL features at once (single COM call)
            sw = Stopwatch.StartNew();
            FeatureManager featMgr = doc.FeatureManager;
            object[] allFeaturesRaw = featMgr.GetFeatures(false) as object[];
            sw.Stop();
            timers.AddTicks("GetFeatures", sw.ElapsedTicks);

            if (allFeaturesRaw == null || allFeaturesRaw.Length == 0)
            {
                prof?.Mark("no_features_from_manager");
                return new Dictionary<string, object>
                {
                    ["document_title"] = documentTitle,
                    ["document_path"] = documentPath,
                    ["feature_count"] = 0,
                    ["features"] = new List<Dictionary<string, object>>()
                };
            }

            int totalRawFeatures = allFeaturesRaw.Length;
            prof?.Mark($"got_all_features: {totalRawFeatures}");

            // Step 3: Extract ALL properties AND relationships in PARALLEL
            // NOTE: We partition the raw object[] and cast to Feature inside tasks.
            // This parallelizes the COM QueryInterface calls that happen during casting.
            // Using Feature references as dictionary keys eliminates all GetID() calls!
            sw = Stopwatch.StartNew();
            var featureDataByRef = new ConcurrentDictionary<Feature, FeatureData>();
            var parallelTimers = new ConcurrentDictionary<int, long>();
            var taskStartDelays = new ConcurrentDictionary<int, long>();
            var extractedFeatures = new ConcurrentBag<Feature>();

            // Parallel extraction of properties AND relationships
            // Use explicit partitioning to guarantee exactly MAX_PARALLELISM threads.
            // Parallel.ForEach with MaxDegreeOfParallelism is a "soft" limit - when threads
            // block on COM marshaling (STA), the thread pool injects more threads.
            // Explicit partitioning ensures exactly N tasks processing N partitions.
            var partitions = System.Collections.Concurrent.Partitioner
                .Create(allFeaturesRaw, EnumerablePartitionerOptions.NoBuffering)
                .GetPartitions(MAX_PARALLELISM);

            long tasksStartTicks = sw.ElapsedTicks;
            var tasks = partitions.Select(partition => Task.Run(() =>
            {
                long taskActualStartTicks = sw.ElapsedTicks;
                int threadId = System.Threading.Thread.CurrentThread.ManagedThreadId;
                taskStartDelays[threadId] = taskActualStartTicks - tasksStartTicks;
                
                var taskSw = Stopwatch.StartNew();
                var localFeatures = new List<Feature>();
                using (partition)
                {
                    while (partition.MoveNext())
                    {
                        // Cast happens inside parallel task - parallelizes COM QueryInterface
                        Feature feat = partition.Current as Feature;
                        if (feat != null)
                        {
                            localFeatures.Add(feat);
                            var data = ExtractFeatureDataWithRelationships(feat, featMgr);
                            featureDataByRef[feat] = data;  // Use Feature reference as key, not ID
                        }
                    }
                }
                // Add to concurrent bag for RCW preservation
                foreach (var f in localFeatures)
                    extractedFeatures.Add(f);
                    
                taskSw.Stop();
                parallelTimers[threadId] = taskSw.ElapsedTicks;
            })).ToArray();

            Task.WaitAll(tasks);
            sw.Stop();
            timers.AddTicks("ParallelExtraction", sw.ElapsedTicks);

            // Keep this document's Feature RCWs alive for reuse on the next walk.
            foreach (Feature f in extractedFeatures)
                ctx.Preserve.Features.Add(f);

            // Optional: inject a synthetic cycle for testing cycle detection (root only).
            if (InjectCycleForTesting && isRoot)
                InjectTestCycle(featureDataByRef);

            // Log parallel timing breakdown (root only — subpart walks stay quiet).
            if (isRoot)
            {
                Console.WriteLine($"[PROFILE] ParallelExtraction: {featureDataByRef.Count} features, {parallelTimers.Count} threads");
                foreach (var kvp in parallelTimers)
                {
                    double workMs = (double)kvp.Value * 1000.0 / Stopwatch.Frequency;
                    double delayMs = taskStartDelays.TryGetValue(kvp.Key, out long delayTicks)
                        ? (double)delayTicks * 1000.0 / Stopwatch.Frequency
                        : 0;
                    Console.WriteLine($"[PROFILE]   Thread {kvp.Key}: {workMs:F1}ms work, {delayMs:F1}ms start delay");
                }
            }

            // Fetch all errors via bulk GetWhatsWrong() as a flat list. This is a property of
            // the active document, so only the root walk runs it; subpart trees carry no error
            // info (error_count/warning_count/feature_errors stay zero/empty).
            if (isRoot)
            {
                var errorsResult = CollectFeatureErrors(doc, featureDataByRef);
                errorCount = errorsResult.ErrorCount;
                warningCount = errorsResult.WarningCount;
                featureErrors = errorsResult.Entries;
            }

            prof?.Mark($"parallel_extract_done: {featureDataByRef.Count} features, errors={errorCount}, warnings={warningCount}");

            // Step 4: Reconstruct tree using pre-extracted relationships (ZERO COM calls!)
            sw = Stopwatch.StartNew();
            var result = ReconstructTreeFromExtractedData(
                documentTitle,
                documentPath,
                firstFeature,  // Pass Feature reference, not ID
                featureDataByRef,
                timers);
            sw.Stop();
            timers.AddTicks("ReconstructTree", sw.ElapsedTicks);

            // Log profiling breakdown (root only — subpart walks stay quiet).
            if (isRoot)
            {
                Console.WriteLine($"[PROFILE] WalkDocument(run={runNumber}) | breakdown: " +
                    $"GetFirstFeature={timers.GetMs("GetFirstFeature")}ms, " +
                    $"GetFeatures={timers.GetMs("GetFeatures")}ms, " +
                    $"ParallelExtraction={timers.GetMs("ParallelExtraction")}ms, " +
                    $"ReconstructTree={timers.GetMs("ReconstructTree")}ms");
                Console.WriteLine($"[PROFILE] ReconstructTree internal: " +
                    $"WalkFlatList={timers.GetMs("WalkFlatList")}ms, " +
                    $"BuildSubFeatures={timers.GetMs("BuildSubFeatures")}ms, " +
                    $"ProcessFolders={timers.GetMs("ProcessFolders")}ms");
            }

            // For an assembly, descend into each component and attach its subpart tree to the
            // matching node in this document's own feature list.
            if (doc is AssemblyDoc asm
                && result["features"] is List<Dictionary<string, object>> topFeatures)
            {
                ExpandAssemblyComponents(asm, topFeatures, depth, ctx);
            }

            prof?.Done("complete");

            return result;
        }

        /// <summary>
        /// For an assembly's top-level feature list, attach each component's referenced
        /// feature tree as a "subpart". Matches feature dicts to components by name
        /// (a component node's name equals IComponent2.Name2). Recurses into sub-assemblies.
        /// </summary>
        private void ExpandAssemblyComponents(
            AssemblyDoc asm,
            List<Dictionary<string, object>> features,
            int depth,
            WalkContext ctx)
        {
            object[] comps = asm.GetComponents(true) as object[];
            if (comps == null || comps.Length == 0)
                return;

            var byName = new Dictionary<string, IComponent2>();
            foreach (object o in comps)
            {
                IComponent2 comp = o as IComponent2;
                if (comp != null && comp.Name2 != null)
                    byName[comp.Name2] = comp;
            }

            AttachSubparts(features, byName, depth, ctx);
        }

        /// <summary>
        /// Recurse the (possibly folder-nested) feature list, attaching a "subpart" to
        /// any node whose name matches a top-level component.
        /// </summary>
        private void AttachSubparts(
            List<Dictionary<string, object>> features,
            Dictionary<string, IComponent2> byName,
            int depth,
            WalkContext ctx)
        {
            foreach (var featDict in features)
            {
                if (featDict.TryGetValue("name", out object nameObj)
                    && nameObj is string name
                    && byName.TryGetValue(name, out IComponent2 comp))
                {
                    featDict["subpart"] = DescendComponent(comp, depth, ctx);
                }

                if (featDict.TryGetValue("children", out object childObj)
                    && childObj is List<Dictionary<string, object>> children)
                {
                    AttachSubparts(children, byName, depth, ctx);
                }
            }
        }

        /// <summary>
        /// Walk one component's referenced document into a subpart tree, or return a
        /// stub when it is a duplicate, capped, unresolved, or errors. The unique-document
        /// budget is MAX_SUBPARTS (== ctx.Seen.Count); duplicates do not consume it.
        ///
        /// ctx.Seen maps each expanded document's "path::config" key to the authoritative
        /// title (GetTitle) recorded at its first expansion, so a duplicate stub reuses that
        /// exact title instead of falling back to the filename. Stubs for genuine failures
        /// (capped, unresolved, error) have no loaded document and so keep the filename — the
        /// only title available without a successful walk.
        /// </summary>
        private Dictionary<string, object> DescendComponent(IComponent2 comp, int depth, WalkContext ctx)
        {
            string config = comp.ReferencedConfiguration;
            string path = comp.GetPathName();
            // Name and location are always cheap (no document load) and are attached to
            // every node — even non-expanded stubs — so a capped/duplicate/unresolved
            // component stays identifiable and locatable. Only the feature details are
            // withheld outside the limit.
            string title = System.IO.Path.GetFileName(path);
            string key = path + "::" + config;

            if (ctx.Seen.TryGetValue(key, out string expandedTitle))
                return new Dictionary<string, object>
                {
                    ["expanded"] = false,
                    ["reason"] = "duplicate",
                    // Reuse the title from the instance that was expanded, so the duplicate
                    // stub names the part exactly as its expanded twin does.
                    ["document_title"] = expandedTitle,
                    ["document_path"] = path,
                    ["configuration"] = config,
                };

            if (ctx.Seen.Count >= MAX_SUBPARTS || depth >= MAX_DEPTH)
                return new Dictionary<string, object>
                {
                    ["expanded"] = false,
                    ["reason"] = "limit_reached",
                    ["document_title"] = title,
                    ["document_path"] = path,
                    ["configuration"] = config,
                };

            ModelDoc2 sub = comp.GetModelDoc2() as ModelDoc2;
            if (sub == null)
                return new Dictionary<string, object>
                {
                    ["expanded"] = false,
                    ["reason"] = "not_resolved",
                    ["document_title"] = title,
                    ["document_path"] = path,
                    ["configuration"] = config,
                };

            try
            {
                // Record the authoritative title now (before the walk, so the recursion
                // guard is in place) — a later duplicate of this same doc reuses it.
                string subTitle = sub.GetTitle();
                ctx.Seen[key] = subTitle;
                // Walk the component's document one level deeper. WalkDocument itself
                // descends further if this component is a sub-assembly.
                Dictionary<string, object> tree = WalkDocument(
                    sub, isRoot: false, depth + 1, ctx, out _, out _, out _);

                return new Dictionary<string, object>
                {
                    ["expanded"] = true,
                    ["document_title"] = subTitle,
                    ["document_path"] = tree["document_path"],
                    ["configuration"] = config,
                    ["feature_count"] = tree["feature_count"],
                    ["features"] = tree["features"],
                };
            }
            catch (Exception ex)
            {
                return new Dictionary<string, object>
                {
                    ["expanded"] = false,
                    ["reason"] = "error: " + ex.Message,
                    ["document_title"] = title,
                    ["document_path"] = path,
                    ["configuration"] = config,
                };
            }
        }

        /// <summary>
        /// Extract ALL relevant properties AND relationships from a single feature.
        /// Called in parallel from multiple threads.
        /// Uses Feature references (not IDs) to eliminate GetID() calls.
        /// </summary>
        private FeatureData ExtractFeatureDataWithRelationships(Feature feat, FeatureManager featMgr)
        {
            var data = new FeatureData
            {
                FeatureRef = feat
            };

            try
            {
                // Basic properties (no GetID needed!)
                data.Name = feat.Name;
                data.Type = feat.GetTypeName2();
                data.Suppressed = feat.IsSuppressed();
                data.RolledBack = feat.IsRolledBack();

                // Check if internal feature
                data.IsInternal = IsInternalFeature(feat, data.Name);

                // Check if folder
                data.IsFolder = data.Type == "FtrFolder";

                // Relationships: store Feature references directly (no GetID calls!)
                data.NextFeature = feat.GetNextFeature() as Feature;
                data.FirstSubFeature = feat.GetFirstSubFeature() as Feature;
                data.NextSubFeature = feat.GetNextSubFeature() as Feature;
                data.Owner = feat.GetOwnerFeature() as Feature;

                // Folder containment: which folder (if any) contains this feature
                data.OwnerFolder = featMgr.FeatureFolderLocation(feat) as Feature;

                // For copy detection: get parent Feature references (no GetID calls!)
                data.Parents = GetParentFeatures(feat);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[WARN] Failed to extract feature data for '{data.Name}': {ex.Message}");
                data.IsInternal = true;  // Skip problematic features
            }

            return data;
        }

        /// <summary>
        /// Check if a feature is internal (used during parallel extraction).
        /// 
        /// SolidWorks has several types of internal features that should not be exposed:
        /// 1. EndTag features - internal folder boundary markers (names contain "___EndTag___")
        /// 2. Hidden features - features with swIsHiddenInFeatureMgr UI state set
        /// 
        /// Note: EndTag features are undocumented by SolidWorks. They were discovered through
        /// reverse engineering and are NOT caught by GetUIState(swIsHiddenInFeatureMgr).
        /// </summary>
        private static bool IsInternalFeature(Feature feat, string name)
        {
            if (feat == null)
                return true;

            // Filter out EndTag features (internal bookkeeping for folder boundaries)
            // These have names like "Folder2___EndTag___0", "MyFolder___EndTag___1", etc.
            if (name != null && name.Contains("___EndTag___"))
                return true;

            // Use GetUIState to check if feature is hidden in FeatureManager design tree
            // This is the official API way to detect hidden features
            try
            {
                bool isHidden = feat.GetUIState((int)swUIStates_e.swIsHiddenInFeatureMgr);
                if (isHidden)
                    return true;
            }
            catch
            {
                return false;
            }

            return false;
        }

        /// <summary>
        /// Get all parents of a feature as an array of Feature references.
        /// No GetID() calls needed - we use object references for comparison.
        /// </summary>
        private static Feature[] GetParentFeatures(Feature feat)
        {
            var parentFeatures = new List<Feature>();
            if (feat == null)
                return parentFeatures.ToArray();

            try
            {
                object[] parents = feat.GetParents() as object[];
                if (parents != null)
                {
                    foreach (object parent in parents)
                    {
                        Feature parentFeat = parent as Feature;
                        if (parentFeat != null)
                        {
                            parentFeatures.Add(parentFeat);
                        }
                    }
                }
            }
            catch
            {
                // If GetParents fails, return empty array
            }

            return parentFeatures.ToArray();
        }

        /// <summary>
        /// Inject a synthetic cycle into the extracted feature data for testing.
        /// Sets PLOT.NextFeature → Hanger_Plt_Sketch, creating a backlink from
        /// outside the Plot folder to a feature already visited during folder processing.
        /// The top-level cycle detector will catch Hanger_Plt_Sketch as already visited
        /// and break the walk.
        /// </summary>
        private static void InjectTestCycle(ConcurrentDictionary<Feature, FeatureData> featureDataByRef)
        {
            FeatureData plotData = null;
            FeatureData hangerPltSketchData = null;

            foreach (var kvp in featureDataByRef)
            {
                if (kvp.Value.Name == "PLOT")
                    plotData = kvp.Value;
                else if (kvp.Value.Name == "Hanger_Plt_Sketch")
                    hangerPltSketchData = kvp.Value;
            }

            if (plotData == null || hangerPltSketchData == null)
            {
                Console.WriteLine("[INJECT_CYCLE] Could not find PLOT and/or Hanger_Plt_Sketch — skipping cycle injection");
                return;
            }

            Feature originalNext = plotData.NextFeature;
            plotData.NextFeature = hangerPltSketchData.FeatureRef;

            string originalNextName = originalNext != null && featureDataByRef.TryGetValue(originalNext, out var origData)
                ? origData.Name : "(null)";
            Console.WriteLine($"[INJECT_CYCLE] Set PLOT.NextFeature = Hanger_Plt_Sketch (was {originalNextName})");
        }

        #region Cycle Detection Helpers

        /// <summary>
        /// Metadata stored for each visited feature in the traversal dictionary.
        /// Combines the "have we seen this?" check (dictionary key) with traversal
        /// context: discovery order, extracted data, and the edge that led here.
        /// </summary>
        private struct VisitedNodeInfo
        {
            public int Index;           // Discovery order (0-based), always equals position in the contiguous path
            public FeatureData Data;    // Full extracted data for this feature
            public string Edge;         // Edge type that led here: "NextFeature", "FirstSubFeature", "NextSubFeature", "FolderContent"
            public Feature From;        // The feature whose edge led to this one (null for the root)
        }

        /// <summary>
        /// Remove all entries from visited whose Index >= sinceIndex.
        /// Used for backtracking: when exiting a sub-scope (sub-features, folder contents),
        /// remove entries added during that scope so sibling branches start with a clean path.
        /// </summary>
        private static void RemoveVisitedSince(
            Dictionary<Feature, VisitedNodeInfo> visited,
            int sinceIndex)
        {
            var keysToRemove = new List<Feature>();
            foreach (var kv in visited)
            {
                if (kv.Value.Index >= sinceIndex)
                    keysToRemove.Add(kv.Key);
            }
            foreach (var key in keysToRemove)
                visited.Remove(key);
        }

        /// <summary>
        /// Return a stable pointer-style ID for a Feature object.
        /// Uses the .NET object identity hash to cross-reference relationship links in cycle logs.
        /// </summary>
        private static string FeaturePtr(Feature feat)
        {
            if (feat == null) return "null";
            return $"0x{feat.GetHashCode():X8}";
        }

        /// <summary>
        /// Log full extracted FeatureData for a single feature, including its discovery edge.
        /// Prints all properties and relationship pointers (as pointer IDs) for debugging cycles.
        /// This is the exact same data that was fetched in the parallel extraction phase.
        /// </summary>
        private static void LogFeatureExtractedData(VisitedNodeInfo info)
        {
            var data = info.Data;
            string ptr = FeaturePtr(data.FeatureRef);

            Console.WriteLine($"[TREEWALKERROR]   [{info.Index}] Feature[{ptr}] via {info.Edge} from Feature[{FeaturePtr(info.From)}]:");
            Console.WriteLine($"[TREEWALKERROR]     Name='{data.Name}', Type='{data.Type}'");
            Console.WriteLine($"[TREEWALKERROR]     Suppressed={data.Suppressed}, RolledBack={data.RolledBack}");
            Console.WriteLine($"[TREEWALKERROR]     IsInternal={data.IsInternal}, IsFolder={data.IsFolder}");
            Console.WriteLine($"[TREEWALKERROR]     Owner={FeaturePtr(data.Owner)}");

            string parentsStr = "[]";
            if (data.Parents != null && data.Parents.Length > 0)
            {
                parentsStr = "[" + string.Join(", ", data.Parents.Select(p => FeaturePtr(p))) + "]";
            }
            Console.WriteLine($"[TREEWALKERROR]     Parents={parentsStr}");

            Console.WriteLine($"[TREEWALKERROR]     NextFeature={FeaturePtr(data.NextFeature)}");
            Console.WriteLine($"[TREEWALKERROR]     FirstSubFeature={FeaturePtr(data.FirstSubFeature)}");
            Console.WriteLine($"[TREEWALKERROR]     NextSubFeature={FeaturePtr(data.NextSubFeature)}");
        }

        /// <summary>
        /// Log a cycle error using the visited dictionary.
        /// Dumps the cycle portion (from original visit to current) with full extracted data
        /// and edge relationships for each feature.
        /// </summary>
        private static void LogCycleError(
            Dictionary<Feature, VisitedNodeInfo> visited,
            FeatureData cycleFeatureData,
            string edgeType,
            Feature fromFeature)
        {
            Console.WriteLine($"[TREEWALKERROR] Cycle detected!");
            Console.WriteLine($"[TREEWALKERROR] Re-encountered Feature[{FeaturePtr(cycleFeatureData.FeatureRef)}] (Name='{cycleFeatureData.Name}')");
            Console.WriteLine($"[TREEWALKERROR] Reached via {edgeType} from Feature[{FeaturePtr(fromFeature)}]");

            var allEntries = visited.Values.OrderBy(v => v.Index).ToList();
            int cycleStartIndex = -1;

            if (visited.TryGetValue(cycleFeatureData.FeatureRef, out var originalVisit))
            {
                cycleStartIndex = originalVisit.Index;
                Console.WriteLine($"[TREEWALKERROR] Originally visited at index {originalVisit.Index} via {originalVisit.Edge} from Feature[{FeaturePtr(originalVisit.From)}]");
            }

            int cyclePortionCount = cycleStartIndex >= 0 ? allEntries.Count - cycleStartIndex : allEntries.Count;
            Console.WriteLine($"[TREEWALKERROR] Full traversal chain ({allEntries.Count} nodes, cycle portion = last {cyclePortionCount} + back-edge):");

            foreach (var entry in allEntries)
            {
                if (entry.Index == cycleStartIndex)
                {
                    Console.WriteLine($"[TREEWALKERROR]   ---- cycle starts here ----");
                }
                LogFeatureExtractedData(entry);
            }
            Console.WriteLine($"[TREEWALKERROR]   --> back to Feature[{FeaturePtr(cycleFeatureData.FeatureRef)}] via {edgeType}");
        }

        #endregion

        /// <summary>
        /// Discard whatever is currently in the application-wide error-message buffer.
        /// GetErrorMessages is drain-on-read, so this clears stale/cross-document entries
        /// before a rebuild so a subsequent read reflects only the current document.
        /// </summary>
        private static void DrainErrorMessages(ISldWorks swApp)
        {
            object msgs = null, ids = null, types = null;
            swApp.GetErrorMessages(out msgs, out ids, out types);
        }

        /// <summary>
        /// Read the application-wide error-message buffer as a list of message texts.
        /// Call immediately after EditRebuild3 to capture this document's rebuild report.
        /// The buffer is drain-on-read, so this also clears it.
        /// </summary>
        private static List<string> CaptureErrorMessages(ISldWorks swApp)
        {
            var texts = new List<string>();
            object msgsObj = null, idsObj = null, typesObj = null;
            int count = swApp.GetErrorMessages(out msgsObj, out idsObj, out typesObj);
            string[] msgs = msgsObj as string[];
            if (count > 0 && msgs != null)
            {
                for (int i = 0; i < count && i < msgs.Length; i++)
                    texts.Add(msgs[i] ?? "");
            }
            return texts;
        }

        /// <summary>
        /// Fetch all feature errors/warnings via the bulk GetWhatsWrong() API (single COM call)
        /// and return them as a flat list of error entries.
        /// For mate features, also extracts the mated entity (component) names.
        /// One entry per reported issue: a feature reported with both an error and a
        /// warning yields two entries, so the counts match the list one-to-one.
        /// </summary>
        private static (int ErrorCount, int WarningCount, List<Dictionary<string, object>> Entries)
            CollectFeatureErrors(
                ModelDoc2 doc,
                ConcurrentDictionary<Feature, FeatureData> featureDataByRef)
        {
            var emptyResult = (0, 0, new List<Dictionary<string, object>>());

            ModelDocExtension ext = doc.Extension;
            if (ext.GetWhatsWrongCount() == 0)
                return emptyResult;

            object featuresArr = null;
            object errorCodesArr = null;
            object warningsArr = null;
            if (!ext.GetWhatsWrong(out featuresArr, out errorCodesArr, out warningsArr))
                return emptyResult;

            object[] features = featuresArr as object[];
            int[] errorCodes = errorCodesArr as int[];
            bool[] warnings = warningsArr as bool[];

            if (features == null || errorCodes == null || warnings == null)
                return emptyResult;

            int errorCount = 0;
            int warningCount = 0;

            // One entry per reported issue. A feature can legitimately appear more
            // than once (e.g. an error and a warning); errors are a section of their
            // own, not inlined onto feature objects, so multiple rows are fine and the
            // counts above match the list one-to-one.
            var entries = new List<Dictionary<string, object>>();

            for (int i = 0; i < features.Length; i++)
            {
                Feature feat = features[i] as Feature;
                if (feat == null)
                    continue;

                if (errorCodes[i] == 0)
                    continue;

                // Count every reported error/warning
                if (warnings[i])
                    warningCount++;
                else
                    errorCount++;

                // Get feature name and type — prefer pre-extracted data, fall back to COM
                string featureName;
                string featureType;
                if (featureDataByRef.TryGetValue(feat, out var data))
                {
                    featureName = data.Name;
                    featureType = data.Type;
                }
                else
                {
                    featureName = feat.Name;
                    featureType = feat.GetTypeName2();
                }

                var entry = new Dictionary<string, object>
                {
                    ["feature_name"] = featureName,
                    ["error_code"] = errorCodes[i],
                    ["error_message"] = FeatureErrorMapper.GetErrorDescription(errorCodes[i]),
                    ["is_warning"] = warnings[i],
                };

                // For mate features (not MateGroup), extract entity names
                if (featureType.StartsWith("Mate") && featureType != "MateGroup")
                {
                    var entityNames = GetMateEntityNames(feat);
                    if (entityNames.Count > 0)
                        entry["entity_names"] = entityNames;
                }

                entries.Add(entry);
            }

            // Sort: errors first, then warnings; alphabetical by name within each group
            var sortedEntries = entries
                .OrderBy(e => (bool)e["is_warning"])       // false (errors) before true (warnings)
                .ThenBy(e => (string)e["feature_name"])
                .ToList();

            return (errorCount, warningCount, sortedEntries);
        }

        /// <summary>
        /// Get the component names involved in a mate feature.
        /// </summary>
        private static List<string> GetMateEntityNames(Feature feat)
        {
            var names = new List<string>();
            try
            {
                Mate2 swMate = feat.GetSpecificFeature2() as Mate2;
                if (swMate == null)
                    return names;

                int entityCount = swMate.GetMateEntityCount();
                for (int i = 0; i < entityCount; i++)
                {
                    MateEntity2 entity = swMate.MateEntity(i);
                    if (entity == null)
                        continue;
                    Component2 comp = entity.ReferenceComponent as Component2;
                    if (comp != null)
                        names.Add(comp.Name2);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[WARN] Failed to get mate entities for '{feat.Name}': {ex.Message}");
            }
            return names;
        }

        /// <summary>
        /// Reconstruct the feature tree using ONLY pre-extracted data.
        /// This method makes ZERO COM calls - pure in-memory operations.
        /// Uses Feature references instead of IDs for all lookups.
        ///
        /// IMPORTANT: ALL features in the flat traversal are added to output.
        /// The owner check only determines whether we collect sub-features.
        /// Sub-features appear BOTH in the main list AND as children (marked as copies).
        /// </summary>
        private Dictionary<string, object> ReconstructTreeFromExtractedData(
            string documentTitle,
            string documentPath,
            Feature firstFeature,
            ConcurrentDictionary<Feature, FeatureData> featureDataByRef,
            NamedTimers timers)
        {
            var features = new List<Dictionary<string, object>>();
            int totalFeatureCount = 0;
            int internalSkipped = 0;
            int folderCount = 0;

            // Build HashSet of top-level Feature references incrementally as we walk
            // This is needed for copy detection in sub-features
            var topLevelFeatures = new HashSet<Feature>();

            // Unified cycle detection for the entire tree traversal.
            // Single dictionary maps each visited Feature to its discovery metadata:
            // insertion index, extracted data, and the edge+source that led to it.
            // Covers all edge types (NextFeature, FirstSubFeature, NextSubFeature, FolderContent).
            // Entries are added on descent and removed on backtrack (sub-scope exit) so that
            // sibling branches don't see each other's features.
            var visited = new Dictionary<Feature, VisitedNodeInfo>();

            // Walk the flat feature list using pre-extracted NextFeature links
            var sw = Stopwatch.StartNew();
            Feature currentFeature = firstFeature;
            Feature previousFeature = null;

            while (currentFeature != null)
            {
                if (!featureDataByRef.TryGetValue(currentFeature, out var data))
                {
                    break;
                }

                // Cycle detection — in a NextFeature linked list, a cycle means all
                // remaining features loop back through already-visited nodes, so we
                // must stop (there's nowhere to skip to).
                if (visited.ContainsKey(currentFeature))
                {
                    LogCycleError(visited, data, "NextFeature", previousFeature);
                    break;
                }
                visited[currentFeature] = new VisitedNodeInfo
                {
                    Index = visited.Count,
                    Data = data,
                    Edge = "NextFeature",
                    From = previousFeature,
                };

                if (!data.IsInternal)
                {
                    var featDict = data.ToDict();

                    // Add to top-level set (for copy detection in sub-features)
                    topLevelFeatures.Add(currentFeature);

                    // Handle folders specially
                    if (data.IsFolder)
                    {
                        folderCount++;
                        sw.Stop();
                        timers.AddTicks("WalkFlatList", sw.ElapsedTicks);

                        var folderSw = Stopwatch.StartNew();
                        Feature lastFeatureInFolder = null;
                        var folderContents = ProcessFolderContentsFromExtractedData(
                            data, topLevelFeatures, featureDataByRef, ref totalFeatureCount, ref lastFeatureInFolder,
                            visited);
                        folderSw.Stop();
                        timers.AddTicks("ProcessFolders", folderSw.ElapsedTicks);

                        if (folderContents.Count > 0)
                        {
                            featDict["children"] = folderContents;
                        }

                        totalFeatureCount++;
                        features.Add(featDict);

                        // Skip past all features in the folder (they're already processed)
                        if (lastFeatureInFolder != null)
                        {
                            if (featureDataByRef.TryGetValue(lastFeatureInFolder, out var lastData))
                            {
                                currentFeature = lastData.NextFeature;
                                sw = Stopwatch.StartNew();
                                continue;
                            }
                        }

                        sw = Stopwatch.StartNew();
                    }
                    else
                    {
                        // Check if this is a top-level feature (no owner)
                        // Only top-level features collect sub-features
                        if (data.Owner == null)
                        {
                            sw.Stop();
                            timers.AddTicks("WalkFlatList", sw.ElapsedTicks);

                            var subSw = Stopwatch.StartNew();
                            int subCheckpoint = visited.Count;
                            var children = CollectSubFeaturesFromExtractedData(
                                data.FirstSubFeature, currentFeature, topLevelFeatures,
                                featureDataByRef, visited);
                            RemoveVisitedSince(visited, subCheckpoint);
                            subSw.Stop();
                            timers.AddTicks("BuildSubFeatures", subSw.ElapsedTicks);

                            if (children.Count > 0)
                            {
                                featDict["children"] = children;
                            }

                            sw = Stopwatch.StartNew();
                        }

                        // ALWAYS add to output - regardless of owner!
                        // (This matches sequential behavior)
                        totalFeatureCount++;
                        features.Add(featDict);
                    }
                }
                else
                {
                    internalSkipped++;
                }

                // Move to next feature using pre-extracted link (ZERO COM calls!)
                previousFeature = currentFeature;
                currentFeature = data.NextFeature;
            }
            sw.Stop();
            timers.AddTicks("WalkFlatList", sw.ElapsedTicks);

            Console.WriteLine($"[PROFILE] ReconstructTree: features={totalFeatureCount}, folders={folderCount}, skipped={internalSkipped}");

            return new Dictionary<string, object>
            {
                ["document_title"] = documentTitle,
                ["document_path"] = documentPath,
                ["feature_count"] = totalFeatureCount,
                ["features"] = features
            };
        }

        /// <summary>
        /// Collect sub-features recursively using pre-extracted data (ZERO COM calls).
        /// Uses Feature references instead of IDs for all lookups.
        /// Uses the unified visited dictionary from the top-level tree traversal for cycle detection.
        /// On cycle detection, the cyclic sub-feature is skipped (not added to output) and
        /// traversal continues with the next sibling.
        /// </summary>
        private List<Dictionary<string, object>> CollectSubFeaturesFromExtractedData(
            Feature firstSubFeature,
            Feature parentFeature,
            HashSet<Feature> topLevelFeatures,
            ConcurrentDictionary<Feature, FeatureData> featureDataByRef,
            Dictionary<Feature, VisitedNodeInfo> visited)
        {
            var subFeatures = new List<Dictionary<string, object>>();

            Feature currentFeature = firstSubFeature;
            bool isFirst = true;

            while (currentFeature != null)
            {
                if (!featureDataByRef.TryGetValue(currentFeature, out var data))
                {
                    break;  // Feature not found
                }

                if (!data.IsInternal)
                {
                    bool isCopy = false;
                    string originalName = null;

                    // Check copy status FIRST — copies are expected duplicates of
                    // top-level features, not cycles. They don't get added to visited.
                    if (topLevelFeatures.Contains(currentFeature))
                    {
                        isCopy = true;
                        originalName = data.Name;
                    }
                    else
                    {
                        // Check copy pattern using pre-extracted parent references
                        var originalData = GetOriginalFeatureIfCopy(data, topLevelFeatures, featureDataByRef);
                        if (originalData != null)
                        {
                            isCopy = true;
                            originalName = originalData.Name;
                        }
                    }

                    if (isCopy)
                    {
                        var copyDict = new Dictionary<string, object>
                        {
                            ["is_copy"] = true,
                            ["original_name"] = originalName,
                        };
                        subFeatures.Add(copyDict);
                    }
                    else
                    {
                        string edgeType = isFirst ? "FirstSubFeature" : "NextSubFeature";

                        // Cycle detection for non-copy features.
                        // In a NextSubFeature linked list, a cycle means all remaining
                        // siblings loop back through visited nodes — we must break.
                        if (visited.ContainsKey(currentFeature))
                        {
                            LogCycleError(visited, data, edgeType, parentFeature);
                            break;
                        }
                        visited[currentFeature] = new VisitedNodeInfo
                        {
                            Index = visited.Count,
                            Data = data,
                            Edge = edgeType,
                            From = parentFeature,
                        };

                        var subFeatDict = data.ToDict();

                        // Recursively collect children using pre-extracted FirstSubFeature.
                        // Checkpoint/restore so this feature's children don't pollute the
                        // visited set when we move to the next sibling.
                        int childCheckpoint = visited.Count;
                        var children = CollectSubFeaturesFromExtractedData(
                            data.FirstSubFeature, currentFeature, topLevelFeatures,
                            featureDataByRef, visited);
                        RemoveVisitedSince(visited, childCheckpoint);

                        if (children.Count > 0)
                        {
                            subFeatDict["children"] = children;
                        }

                        subFeatures.Add(subFeatDict);
                    }
                }

                // Move to next sibling using pre-extracted link (ZERO COM calls!)
                isFirst = false;
                parentFeature = currentFeature;  // "from" for the next sibling
                currentFeature = data.NextSubFeature;
            }

            return subFeatures;
        }

        /// <summary>
        /// Check if a sub-feature is a copy/reference to an original feature.
        /// Uses pre-extracted parent Feature references - no COM calls needed.
        /// </summary>
        private FeatureData GetOriginalFeatureIfCopy(
            FeatureData subFeatData,
            HashSet<Feature> topLevelFeatures,
            ConcurrentDictionary<Feature, FeatureData> featureDataByRef)
        {
            // Criterion 1: Sub-feature must NOT be in the top-level list
            if (topLevelFeatures.Contains(subFeatData.FeatureRef))
                return null;

            // Get pre-extracted parents
            Feature[] parents = subFeatData.Parents;
            if (parents == null || parents.Length == 0)
                return null;

            Feature firstParent = parents[0];
            if (!featureDataByRef.TryGetValue(firstParent, out var firstParentData))
                return null;

            // Criterion 2: Check if parents of first parent equals remaining parents
            Feature[] firstParentParents = firstParentData.Parents ?? new Feature[0];

            // Remove first element from firstParentParents
            Feature[] firstParentParentsSliced;
            if (firstParentParents.Length < 2)
            {
                firstParentParentsSliced = new Feature[0];
            }
            else
            {
                firstParentParentsSliced = new Feature[firstParentParents.Length - 1];
                Array.Copy(firstParentParents, 1, firstParentParentsSliced, 0, firstParentParentsSliced.Length);
            }

            // Build array of remaining parents
            Feature[] remainingParents = new Feature[parents.Length - 1];
            for (int i = 1; i < parents.Length; i++)
            {
                remainingParents[i - 1] = parents[i];
            }

            // Compare arrays using reference equality
            if (firstParentParentsSliced.Length != remainingParents.Length)
                return null;

            for (int i = 0; i < firstParentParentsSliced.Length; i++)
            {
                if (!object.ReferenceEquals(firstParentParentsSliced[i], remainingParents[i]))
                    return null;
            }

            // Criterion 3: Check if name matches pattern "...<number>"
            if (subFeatData.Name == null || !Regex.IsMatch(subFeatData.Name, @"<\d+>$"))
                return null;

            // All criteria met - this is a copy, return the first parent as the original
            return firstParentData;
        }

        /// <summary>
        /// Process folder contents using pre-extracted data. ZERO COM calls needed.
        /// Walks the pre-extracted NextFeature chain from the folder and uses the pre-extracted
        /// OwnerFolder (from FeatureFolderLocation) to identify direct children. The folder's
        /// NextFeature points to the first feature inside it. We process features whose
        /// OwnerFolder matches this folder and stop when we encounter a non-internal feature
        /// with a different OwnerFolder. Nested folders are recursed into and skipped past.
        /// Uses the unified visited dictionary from the top-level tree traversal for cycle detection.
        /// Folder items stay in visited (they're part of the linear chain); only sub-feature
        /// collection uses checkpoint/restore (sub-features are branches, not part of the chain).
        /// </summary>
        private List<Dictionary<string, object>> ProcessFolderContentsFromExtractedData(
            FeatureData folderData,
            HashSet<Feature> topLevelFeatures,
            ConcurrentDictionary<Feature, FeatureData> featureDataByRef,
            ref int totalFeatureCount,
            ref Feature lastFeatureInFolder,
            Dictionary<Feature, VisitedNodeInfo> visited)
        {
            if (!folderData.IsFolder || folderData.FeatureRef == null)
                return new List<Dictionary<string, object>>();

            var folderContents = new List<Dictionary<string, object>>();
            lastFeatureInFolder = null;

            // Walk NextFeature chain from the folder. The folder's NextFeature points to the
            // first feature inside it. We use pre-extracted OwnerFolder to identify direct
            // children and stop when we exit the folder's scope.
            Feature current = folderData.NextFeature;

            while (current != null)
            {
                if (!featureDataByRef.TryGetValue(current, out var data))
                    break;

                // Skip internal features (EndTags, hidden features)
                if (data.IsInternal)
                {
                    current = data.NextFeature;
                    continue;
                }

                // Check if this feature belongs to this folder
                if (!object.ReferenceEquals(data.OwnerFolder, folderData.FeatureRef))
                    break;

                lastFeatureInFolder = current;

                // Cycle detection — folder items are part of the linear NextFeature chain,
                // so a revisit means a true cycle; we must stop.
                if (visited.ContainsKey(current))
                {
                    LogCycleError(visited, data, "FolderContent", folderData.FeatureRef);
                    break;
                }

                visited[current] = new VisitedNodeInfo
                {
                    Index = visited.Count,
                    Data = data,
                    Edge = "FolderContent",
                    From = folderData.FeatureRef,
                };

                var featDict = data.ToDict();

                // Register as top-level within folder context
                topLevelFeatures.Add(current);
                totalFeatureCount++;

                // Handle nested folders
                if (data.IsFolder)
                {
                    Feature subFolderLastFeature = null;
                    var nestedContents = ProcessFolderContentsFromExtractedData(
                        data, topLevelFeatures, featureDataByRef,
                        ref totalFeatureCount, ref subFolderLastFeature,
                        visited);
                    if (nestedContents.Count > 0)
                    {
                        featDict["children"] = nestedContents;
                    }

                    folderContents.Add(featDict);

                    // Skip past the nested folder's contents
                    if (subFolderLastFeature != null)
                    {
                        lastFeatureInFolder = subFolderLastFeature;
                        if (featureDataByRef.TryGetValue(subFolderLastFeature, out var lastData))
                            current = lastData.NextFeature;
                        else
                            break;
                    }
                    else
                    {
                        // Empty nested folder — advance from the folder itself
                        current = data.NextFeature;
                    }
                    continue;
                }
                else
                {
                    // Collect sub-features using pre-extracted data.
                    // Sub-features are branches off the linear chain, so checkpoint/restore
                    // to keep them from polluting the visited set.
                    int subCheckpoint = visited.Count;
                    var children = CollectSubFeaturesFromExtractedData(
                        data.FirstSubFeature, current, topLevelFeatures,
                        featureDataByRef, visited);
                    RemoveVisitedSince(visited, subCheckpoint);
                    if (children.Count > 0)
                    {
                        featDict["children"] = children;
                    }
                }

                folderContents.Add(featDict);
                current = data.NextFeature;
            }

            return folderContents;
        }
    }
}
