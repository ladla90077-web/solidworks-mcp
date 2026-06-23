using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Threading;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace CosmonSWService
{
    /// <summary>
    /// Router implementation for SolidWorks operations.
    /// 
    /// This router handles SolidWorks-specific tasks like retrieving model state.
    /// It manages the SolidWorks connection and delegates to ParallelModelStateManager.
    /// 
    /// The SolidWorks connection is initialized lazily in PreTaskCheck and reused across tasks.
    /// If the connection is lost, it will attempt to reconnect on the next PreTaskCheck.
    /// </summary>
    public class SolidWorksRouter : ITaskRouter, IDisposable
    {
        // Task names
        public const string TASK_GET_MODEL_STATE_PARALLEL = "get_model_state_parallel";
        public const string TASK_GET_SELECTION_INFO = "get_selection_info";
        public const string TASK_DRAIN_ERROR_MESSAGES = "drain_error_messages";

        // Test-only task names (for cleanup verification tests)
        public const string TASK_HANG_FOREVER = "hang_forever";
        public const string TASK_CHECK_FLAGS = "check_flags";
        public const string TASK_SET_FLAGS_DISABLED = "set_flags_disabled";
        public const string TASK_TEST_DOC_SWITCH_WITH_FLAGS = "test_doc_switch_with_flags";
        public const string TASK_FAIL_WITH_OUTPUT = "fail_with_output";
        public const string TASK_FORCE_DISCONNECT = "force_disconnect";
        public const string TASK_ACTIVATE_DOCUMENT = "activate_document";
        public const string TASK_PROBE_PARALLELISM = "probe_parallelism";

        // State stored for reuse across tasks
        private SolidWorksConnection _connection;
        private readonly ParallelModelStateManager _parallelModelStateManager;
        private readonly SelectionManager _selectionManager;
        private readonly DrawingStateManager _drawingStateManager;

        // Static constructor for assembly resolution - runs when class is first accessed
        // SolidWorks API path is baked in at compile time via CompileTimeConfig.cs
        static SolidWorksRouter()
        {
            AppDomain.CurrentDomain.AssemblyResolve += (sender, args) =>
            {
                string swPath = CompileTimeConfig.SolidWorksApiPath;
                string assemblyName = new AssemblyName(args.Name).Name;
                string assemblyPath = Path.Combine(swPath, assemblyName + ".dll");

                if (File.Exists(assemblyPath))
                {
                    return Assembly.LoadFrom(assemblyPath);
                }
                return null;
            };
        }

        /// <summary>
        /// Create a new SolidWorksRouter.
        /// Connection will be initialized lazily in PreTaskCheck.
        /// </summary>
        public SolidWorksRouter()
        {
            // Managers resolve connection lazily via Func, so they never go stale after reconnection
            _parallelModelStateManager = new ParallelModelStateManager(() => _connection);
            _selectionManager = new SelectionManager(() => _connection);
            _drawingStateManager = new DrawingStateManager(() => _connection);
        }

        public TaskCheckResult PreTaskCheck(Dictionary<string, object> preTaskCheckArgs)
        {
            // Initialize connection if not already done (lazy initialization)
            if (_connection == null)
            {
                try
                {
                    Console.WriteLine("[DEBUG] Initializing SolidWorks connection...");
                    Console.Out.Flush();
                    _connection = new SolidWorksConnection();
                    _connection.Connect();
                    Console.WriteLine("[DEBUG] SolidWorks connected successfully");
                    Console.Out.Flush();
                }
                catch (Exception ex)
                {
                    return TaskCheckResult.Failure(
                        $"Failed to connect to SolidWorks: {ex.Message}"
                    );
                }
            }

            // Check if still connected to SolidWorks - attempt reconnection if lost
            if (!_connection.IsConnected)
            {
                Console.WriteLine("[WARN] SolidWorks connection lost, attempting to reconnect...");
                Console.Out.Flush();

                // Dispose old connection and try again
                _connection.Dispose();
                _connection = null;

                try
                {
                    _connection = new SolidWorksConnection();
                    _connection.Connect();
                    Console.WriteLine("[INFO] SolidWorks reconnected successfully");
                    Console.Out.Flush();
                }
                catch (Exception ex)
                {
                    return TaskCheckResult.Failure(
                        $"Failed to reconnect to SolidWorks: {ex.Message}"
                    );
                }
            }

            // Doc-less tasks (probe_parallelism, force_disconnect) need to run
            // even without an active document; doc-required tasks call
            // RequireActiveDocument() themselves.
            if (_connection.SwApp == null)
            {
                return TaskCheckResult.Failure(
                    "SolidWorks application instance is null"
                );
            }

            return TaskCheckResult.Success();
        }

        public Dictionary<string, object> ExecuteTask(string taskName, Dictionary<string, object> taskArgs)
        {
            try
            {
                switch (taskName)
                {
                    case TASK_GET_MODEL_STATE_PARALLEL:
                        return ExecuteGetModelState(taskArgs);

                    case TASK_GET_SELECTION_INFO:
                        return ExecuteGetSelectionInfo(taskArgs);

                    case TASK_DRAIN_ERROR_MESSAGES:
                        return ExecuteDrainErrorMessages(taskArgs);

                    // Test-only tasks (for cleanup verification tests)
                    case TASK_HANG_FOREVER:
                        return ExecuteHangForever(taskArgs);

                    case TASK_CHECK_FLAGS:
                        return ExecuteCheckFlags(taskArgs);

                    case TASK_SET_FLAGS_DISABLED:
                        return ExecuteSetFlagsDisabled(taskArgs);

                    case TASK_TEST_DOC_SWITCH_WITH_FLAGS:
                        return ExecuteTestDocSwitchWithFlags(taskArgs);

                    case TASK_FAIL_WITH_OUTPUT:
                        return ExecuteFailWithOutput(taskArgs);

                    case TASK_FORCE_DISCONNECT:
                        return ExecuteForceDisconnect(taskArgs);

                    case TASK_ACTIVATE_DOCUMENT:
                        return ExecuteActivateDocument(taskArgs);

                    case TASK_PROBE_PARALLELISM:
                        return ExecuteProbeParallelism(taskArgs);

                    default:
                        throw new ArgumentException($"Unknown task: {taskName}");
                }
            }
            catch (Exception ex)
            {
                // Catch all exceptions and return as a result with full stack trace
                Console.Error.WriteLine($"[ERROR] Task '{taskName}' failed: {ex.GetType().FullName}: {ex.Message}");
                Console.Error.WriteLine(ex.StackTrace);
                return BuildErrorResult(ex);
            }
        }

        /// <summary>
        /// Build an error result dictionary from an exception.
        /// Format matches CSharpErrorOutput in Python for unified error handling.
        /// </summary>
        private static Dictionary<string, object> BuildErrorResult(Exception ex)
        {
            // Extract structured stack trace information
            var stackFrames = new List<Dictionary<string, object>>();
            var stackTrace = new StackTrace(ex, true);

            for (int i = 0; i < stackTrace.FrameCount; i++)
            {
                var frame = stackTrace.GetFrame(i);
                if (frame == null) continue;

                var method = frame.GetMethod();
                if (method == null) continue;

                var frameDict = new Dictionary<string, object>
                {
                    ["file_name"] = frame.GetFileName() ?? "",
                    ["method_name"] = method.Name,
                    ["declaring_type"] = method.DeclaringType?.FullName ?? "",
                    ["line_number"] = frame.GetFileLineNumber(),
                    ["column_number"] = frame.GetFileColumnNumber()
                };

                stackFrames.Add(frameDict);
            }

            // Return in CSharpErrorOutput format (status discriminator)
            return new Dictionary<string, object>
            {
                ["status"] = "error",
                ["error_type"] = ex.GetType().FullName,
                ["message"] = ex.Message,
                ["stack_trace"] = ex.StackTrace ?? "",
                ["source"] = ex.Source ?? "",
                ["help_link"] = ex.HelpLink ?? "",
                ["stack_frames"] = stackFrames
            };
        }

        public IEnumerable<string> GetAvailableTasks()
        {
            return new[]
            {
                TASK_GET_MODEL_STATE_PARALLEL,
                TASK_GET_SELECTION_INFO,
                TASK_DRAIN_ERROR_MESSAGES,
                // Test-only tasks
                TASK_HANG_FOREVER,
                TASK_CHECK_FLAGS,
                TASK_SET_FLAGS_DISABLED,
                TASK_TEST_DOC_SWITCH_WITH_FLAGS,
                TASK_FAIL_WITH_OUTPUT,
                TASK_FORCE_DISCONNECT,
                TASK_ACTIVATE_DOCUMENT,
                TASK_PROBE_PARALLELISM
            };
        }

        /// <summary>
        /// Execute get_model_state_parallel task. Routes by active document type:
        /// drawings -> ExecuteGetDrawingState; parts/assemblies -> ExecuteGetFeatureTreeParallel.
        /// </summary>
        private Dictionary<string, object> ExecuteGetModelState(Dictionary<string, object> args)
        {
            var docCheck = RequireActiveDocument();
            if (docCheck != null)
                return docCheck;

            ModelDoc2 doc = _connection.SwApp.ActiveDoc as ModelDoc2;
            if ((doc as IDrawingDoc) != null)
                return ExecuteGetDrawingState(args);

            return ExecuteGetFeatureTreeParallel(args);
        }

        /// <summary>
        /// Parallel feature tree walking (part/assembly documents).
        /// Args: { "subcomponent": string } (optional) — when set, return that named
        /// assembly component's referenced tree instead of the active document's own tree.
        /// </summary>
        private Dictionary<string, object> ExecuteGetFeatureTreeParallel(Dictionary<string, object> args)
        {
            var docCheck = RequireActiveDocument();
            if (docCheck != null)
                return docCheck;

            string subcomponent = GetStringArg(args, "subcomponent", null);
            if (!string.IsNullOrEmpty(subcomponent))
                return _parallelModelStateManager.GetModelState(subcomponent);

            return _parallelModelStateManager.GetModelState();
        }

        /// <summary>
        /// Extract the state of the active drawing document (sheets, views, dimensions, ...).
        /// </summary>
        private Dictionary<string, object> ExecuteGetDrawingState(Dictionary<string, object> args)
        {
            var docCheck = RequireActiveDocument();
            if (docCheck != null)
                return docCheck;

            return _drawingStateManager.GetDrawingState();
        }

        /// <summary>
        /// Execute get_selection_info task - get current selections.
        /// Args: { "save_selection": bool } (optional, default false)
        /// Returns: { "mode": "detailed"|"summary", "total_count": int, "selections": [...], "summary": {...} }
        /// </summary>
        private Dictionary<string, object> ExecuteGetSelectionInfo(Dictionary<string, object> args)
        {
            var docCheck = RequireActiveDocument();
            if (docCheck != null)
                return docCheck;

            bool saveSelection = GetBoolArg(args, "save_selection", false);

            var swApp = _connection.SwApp;
            ModelDoc2 doc = swApp.ActiveDoc as ModelDoc2;

            // Wrap in PerformanceOptimizationScope for consistency with other operations
            // Note: SaveCurrentSelectionToNexusLastSelection handles temporarily re-enabling
            // the feature tree when needed for selection set operations
            using (new PerformanceOptimizationScope(swApp, doc))
            {
                // Get selections using the dedicated SelectionManager
                // Returns dict with mode, total_count, selections, and optionally summary
                var result = _selectionManager.GetCurrentSelections();

                // Optionally save the selection to Nexus_Last_Selection
                if (saveSelection)
                {
                    _selectionManager.SaveCurrentSelectionToNexusLastSelection();
                }

                return result;
            }
        }

        /// <summary>
        /// Drain the application-wide GetErrorMessages buffer and return its contents.
        ///
        /// GetErrorMessages is a drain-on-read, app-wide buffer. Calling this immediately
        /// before user code runs captures whatever residual is sitting in the buffer at
        /// that moment — errors produced by the user's own prior actions (manual edits,
        /// earlier steps) — which would otherwise be silently discarded by the model-state
        /// walk's pre-rebuild drain. Does not require an active document (the buffer is
        /// application-wide, not per-document).
        /// </summary>
        private Dictionary<string, object> ExecuteDrainErrorMessages(Dictionary<string, object> args)
        {
            ISldWorks swApp = _connection.SwApp;

            var texts = new List<string>();
            object msgsObj = null, idsObj = null, typesObj = null;
            int count = swApp.GetErrorMessages(out msgsObj, out idsObj, out typesObj);
            string[] msgs = msgsObj as string[];
            if (count > 0 && msgs != null)
            {
                for (int i = 0; i < count && i < msgs.Length; i++)
                    texts.Add(msgs[i] ?? "");
            }

            return new Dictionary<string, object>
            {
                ["raw_error_messages"] = texts
            };
        }

        /// <summary>
        /// Return a ReportedError result dict if no document is open, else null.
        /// </summary>
        private Dictionary<string, object> RequireActiveDocument()
        {
            var swApp = _connection.SwApp;
            if (swApp?.ActiveDoc != null)
                return null;

            var availableTitles = new List<string>();
            if (swApp != null)
            {
                object[] docs = (object[])swApp.GetDocuments();
                if (docs != null)
                {
                    foreach (object docObj in docs)
                    {
                        ModelDoc2 openDoc = docObj as ModelDoc2;
                        if (openDoc != null)
                            availableTitles.Add(openDoc.GetTitle());
                    }
                }
            }

            string availableList = availableTitles.Count > 0
                ? string.Join(", ", availableTitles)
                : "(none)";

            return Protocol.ReportedErrorResult(
                $"No active document is open in SolidWorks. Open documents: [{availableList}]"
            );
        }

        /// <summary>
        /// Helper to get a string argument with a default value.
        /// </summary>
        private static string GetStringArg(Dictionary<string, object> args, string key, string defaultValue)
        {
            if (args == null || !args.ContainsKey(key))
                return defaultValue;

            return args[key]?.ToString() ?? defaultValue;
        }

        /// <summary>
        /// Helper to get a boolean argument with a default value.
        /// </summary>
        private static bool GetBoolArg(Dictionary<string, object> args, string key, bool defaultValue)
        {
            if (args == null || !args.ContainsKey(key))
                return defaultValue;

            try
            {
                return Convert.ToBoolean(args[key]);
            }
            catch
            {
                return defaultValue;
            }
        }

        // =====================================================================
        // Test-only task implementations (for cleanup verification tests)
        // =====================================================================

        /// <summary>
        /// TEST ONLY: Hangs forever in an infinite loop.
        /// 
        /// This is used to test timeout handling and cleanup. When the Python side
        /// times out, it will kill the process. The cleanup tool should then reset
        /// the performance flags that were left in a bad state.
        /// 
        /// If set_flags_first is true, performance flags are set to disabled state
        /// before entering the infinite loop (simulating a crash mid-operation).
        /// 
        /// Args: { "set_flags_first": true } (optional, default false)
        /// Returns: Never returns (hangs forever)
        /// </summary>
        private Dictionary<string, object> ExecuteHangForever(Dictionary<string, object> args)
        {
            bool setFlagsFirst = false;
            if (args != null && args.ContainsKey("set_flags_first"))
            {
                setFlagsFirst = Convert.ToBoolean(args["set_flags_first"]);
            }

            if (setFlagsFirst)
            {
                // Simulate being mid-operation: set performance flags to disabled state
                // This is what happens when PerformanceOptimizationScope is active
                SetPerformanceFlagsDisabled();
            }

            // Infinite loop - only way out is process termination
            while (true)
            {
                Thread.Sleep(100);
            }

            // Never reached
        }

        /// <summary>
        /// TEST ONLY: Check the current state of performance optimization flags.
        /// 
        /// This does NOT wrap the operation in PerformanceOptimizationScope, so it
        /// returns the actual current state of the flags. Used to verify that the
        /// cleanup tool correctly reset the flags.
        /// 
        /// Returns: {
        ///     "command_in_progress": bool,
        ///     "graphics_update_enabled": bool | null,
        ///     "feature_tree_enabled": bool | null,
        ///     "has_active_document": bool,
        ///     "window_enabled": bool
        /// }
        /// </summary>
        private Dictionary<string, object> ExecuteCheckFlags(Dictionary<string, object> args)
        {
            var swApp = _connection.SwApp;
            
            // Use shared helper to check all flags
            var status = PerformanceFlagsHelper.CheckFlags(swApp);
            
            // Convert to dictionary for JSON serialization
            return new Dictionary<string, object>
            {
                ["command_in_progress"] = status.CommandInProgress,
                ["window_enabled"] = status.WindowEnabled,
                ["has_active_document"] = status.HasActiveDocument,
                ["graphics_update_enabled"] = status.GraphicsUpdateEnabled,
                ["feature_tree_enabled"] = status.FeatureTreeEnabled
            };
        }

        /// <summary>
        /// TEST ONLY: Set performance flags to disabled state (simulating mid-operation crash).
        /// 
        /// This sets the same flags that PerformanceOptimizationScope sets, but without
        /// the automatic cleanup. Used to set up a degraded state for testing cleanup.
        /// 
        /// Returns: { "flags_set": true }
        /// </summary>
        private Dictionary<string, object> ExecuteSetFlagsDisabled(Dictionary<string, object> args)
        {
            SetPerformanceFlagsDisabled();
            return new Dictionary<string, object>
            {
                ["flags_set"] = true
            };
        }

        /// <summary>
        /// Helper: Set performance flags to their disabled/optimized state.
        /// Uses the shared PerformanceFlagsHelper for consistency with PerformanceOptimizationScope.
        /// </summary>
        private void SetPerformanceFlagsDisabled()
        {
            var swApp = _connection.SwApp;
            ModelDoc2 doc = swApp.ActiveDoc as ModelDoc2;
            
            // Use shared helper (same as PerformanceOptimizationScope)
            PerformanceFlagsHelper.DisableFlags(swApp, doc);
        }

        /// <summary>
        /// TEST ONLY: Test document switching within the optimization scope.
        /// 
        /// This tests the hypothesis that setting performance flags on one document,
        /// switching to another document, and then exiting the scope might cause
        /// the flag reset to fail.
        /// 
        /// Test flow:
        /// 1. Get all open documents (requires at least 2)
        /// 2. Store original active document
        /// 3. Enter PerformanceOptimizationScope (sets CommandInProgress=true, etc.)
        /// 4. Switch to a different document
        /// 5. Exit the scope (Dispose should reset flags)
        /// 6. Check if CommandInProgress was successfully reset
        /// 
        /// Returns: {
        ///     "success": bool,
        ///     "original_document": string,
        ///     "switched_to_document": string,
        ///     "documents_found": int,
        ///     "command_in_progress_before_scope": bool,
        ///     "command_in_progress_after_scope": bool,
        ///     "flags_reset_correctly": bool,
        ///     "error": string | null
        /// }
        /// </summary>
        private Dictionary<string, object> ExecuteTestDocSwitchWithFlags(Dictionary<string, object> args)
        {
            var result = new Dictionary<string, object>();
            var swApp = _connection.SwApp;

            try
            {
                // Step 1: Get all open documents
                object[] docs = (object[])swApp.GetDocuments();
                var documentTitles = new List<string>();
                var documentList = new List<ModelDoc2>();

                if (docs != null)
                {
                    foreach (object docObj in docs)
                    {
                        ModelDoc2 doc = docObj as ModelDoc2;
                        if (doc != null)
                        {
                            string title = doc.GetTitle();
                            documentTitles.Add(title);
                            documentList.Add(doc);
                        }
                    }
                }

                result["documents_found"] = documentList.Count;

                if (documentList.Count < 2)
                {
                    result["success"] = false;
                    result["error"] = $"Need at least 2 open documents, found {documentList.Count}: [{string.Join(", ", documentTitles)}]";
                    return result;
                }

                // Step 2: Store original active document
                ModelDoc2 originalDoc = swApp.ActiveDoc as ModelDoc2;
                string originalTitle = originalDoc?.GetTitle() ?? "(none)";
                result["original_document"] = originalTitle;

                // Find a different document to switch to
                ModelDoc2 targetDoc = null;
                string targetTitle = null;
                foreach (var doc in documentList)
                {
                    string title = doc.GetTitle();
                    if (title != originalTitle)
                    {
                        targetDoc = doc;
                        targetTitle = title;
                        break;
                    }
                }

                if (targetDoc == null)
                {
                    result["success"] = false;
                    result["error"] = "Could not find a different document to switch to";
                    return result;
                }

                result["switched_to_document"] = targetTitle;

                // Step 3: Check CommandInProgress before the scope
                bool cipBefore = swApp.CommandInProgress;
                result["command_in_progress_before_scope"] = cipBefore;

                // Step 4: Enter optimization scope, switch documents, then exit
                using (new PerformanceOptimizationScope(swApp, originalDoc))
                {
                    // Switch to a different document
                    int errors = 0;
                    swApp.ActivateDoc3(
                        targetTitle,
                        false,
                        (int)swRebuildOnActivation_e.swDontRebuildActiveDoc,
                        ref errors
                    );
                }

                // Step 5: Check CommandInProgress after the scope
                bool cipAfter = swApp.CommandInProgress;
                result["command_in_progress_after_scope"] = cipAfter;

                // Step 6: Determine if flags were reset correctly
                bool flagsResetCorrectly = (cipAfter == false);
                result["flags_reset_correctly"] = flagsResetCorrectly;
                result["success"] = true;
                result["error"] = null;

                return result;
            }
            catch (Exception ex)
            {
                result["success"] = false;
                result["error"] = ex.Message;
                return result;
            }
        }

        /// <summary>
        /// TEST ONLY: Write output to stdout, then throw an exception.
        /// 
        /// Used to test that stdout output is included in error logging.
        /// This verifies that _process_response captures stdout context when logging errors.
        /// 
        /// Args: { "lines": 5, "marker": "FAIL_MARKER", "message": "error message" } (all optional)
        /// Never returns (throws InvalidOperationException).
        /// </summary>
        private Dictionary<string, object> ExecuteFailWithOutput(Dictionary<string, object> args)
        {
            int lines = 5;
            string marker = "FAIL_MARKER";
            string message = "Intentional failure after output";

            if (args != null)
            {
                if (args.ContainsKey("lines"))
                {
                    lines = Convert.ToInt32(args["lines"]);
                }
                if (args.ContainsKey("marker"))
                {
                    marker = args["marker"]?.ToString() ?? "FAIL_MARKER";
                }
                if (args.ContainsKey("message"))
                {
                    message = args["message"]?.ToString() ?? "Intentional failure after output";
                }
            }

            // Write distinctive output before failing
            for (int i = 1; i <= lines; i++)
            {
                Console.WriteLine($"[{marker}] Line {i} of {lines}");
            }
            Console.Out.Flush();

            throw new InvalidOperationException(message);
        }

        /// <summary>
        /// TEST ONLY: Poison the current SolidWorks connection by disposing it in-place.
        ///
        /// This calls Dispose() on the connection (which sets _swApp = null internally)
        /// WITHOUT nulling the router's _connection field. This means:
        /// - _connection still exists (non-null)
        /// - _connection.IsConnected returns false (because _swApp is null)
        /// - PreTaskCheck will enter the "connection lost" reconnection path
        /// - A new SolidWorksConnection is created and assigned to _connection
        ///
        /// This is the exact scenario that triggered the original bug: managers that
        /// cached the old connection reference would still see the disposed connection
        /// (with _swApp = null) and throw "Not connected to SolidWorks", even though
        /// the router's _connection field now points to a fresh, working connection.
        ///
        /// Returns: { "disconnected": true }
        /// </summary>
        private Dictionary<string, object> ExecuteForceDisconnect(Dictionary<string, object> args)
        {
            if (_connection != null)
            {
                Console.WriteLine("[TEST] Poisoning SolidWorks connection (Dispose without nulling field)...");
                _connection.Dispose();
                // Intentionally NOT setting _connection = null.
                // This forces the IsConnected == false reconnection path in PreTaskCheck.
            }

            return new Dictionary<string, object>
            {
                ["disconnected"] = true
            };
        }

        /// <summary>
        /// TEST ONLY: Activate an already-open document by title.
        ///
        /// Searches all open documents for one matching the given title and
        /// activates it via ActivateDoc3. Fails if the document is not found.
        ///
        /// Args: { "title": "DocumentName" }
        /// Returns: { "activated": true, "document_title": "DocumentName" }
        /// </summary>
        private Dictionary<string, object> ExecuteActivateDocument(Dictionary<string, object> args)
        {
            if (args == null || !args.ContainsKey("title"))
                throw new ArgumentException("activate_document requires a 'title' argument");

            string requiredTitle = args["title"]?.ToString();
            if (string.IsNullOrEmpty(requiredTitle))
                throw new ArgumentException("'title' argument must be a non-empty string");

            var swApp = _connection.SwApp;
            object[] docs = (object[])swApp.GetDocuments();

            ModelDoc2 targetDoc = null;
            var availableTitles = new List<string>();

            if (docs != null)
            {
                foreach (object docObj in docs)
                {
                    ModelDoc2 doc = docObj as ModelDoc2;
                    if (doc != null)
                    {
                        string title = doc.GetTitle();
                        availableTitles.Add(title);
                        if (title == requiredTitle)
                        {
                            targetDoc = doc;
                        }
                    }
                }
            }

            if (targetDoc == null)
            {
                string availableList = availableTitles.Count > 0
                    ? string.Join(", ", availableTitles)
                    : "(none)";
                throw new InvalidOperationException(
                    $"Document '{requiredTitle}' is not currently open. Available documents: [{availableList}]"
                );
            }

            int errors = 0;
            swApp.ActivateDoc3(
                targetDoc.GetTitle(),
                false,
                (int)swRebuildOnActivation_e.swDontRebuildActiveDoc,
                ref errors
            );

            return new Dictionary<string, object>
            {
                ["activated"] = true,
                ["document_title"] = targetDoc.GetTitle()
            };
        }

        /// <summary>
        /// TEST ONLY: Endpoint that invokes <see cref="ParallelismProbeHelper.RunProbe"/>.
        /// Args: { "current_path": string, "max_path": string, "sleep_ms": int }.
        /// </summary>
        private Dictionary<string, object> ExecuteProbeParallelism(Dictionary<string, object> args)
        {
            if (args == null
                || !args.ContainsKey("current_path")
                || !args.ContainsKey("max_path")
                || !args.ContainsKey("sleep_ms"))
            {
                throw new ArgumentException(
                    "probe_parallelism requires 'current_path', 'max_path', and 'sleep_ms' arguments"
                );
            }

            string currentPath = args["current_path"]?.ToString();
            string maxPath = args["max_path"]?.ToString();
            int sleepMs = Convert.ToInt32(args["sleep_ms"]);

            if (string.IsNullOrEmpty(currentPath) || string.IsNullOrEmpty(maxPath))
                throw new ArgumentException("'current_path' and 'max_path' must be non-empty");

            ParallelismProbeHelper.RunProbe(currentPath, maxPath, sleepMs);

            return new Dictionary<string, object>
            {
                ["ok"] = true
            };
        }

        /// <summary>
        /// Dispose the router and clean up the SolidWorks connection.
        /// </summary>
        public void Dispose()
        {
            if (_connection != null)
            {
                Console.WriteLine("[INFO] Disposing SolidWorks connection...");
                _connection.Dispose();
                _connection = null;
            }
        }
    }
}

