using System;
using System.Collections.Generic;
using System.Diagnostics;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace CosmonSWService
{
    /// <summary>
    /// Manages selection retrieval and persistence in SolidWorks.
    /// Provides selection listing (what is currently selected) and
    /// selection set operations (saving/renaming selections).
    /// </summary>
    public class SelectionManager
    {
        private readonly Func<SolidWorksConnection> _getConnection;

        // Well-known selection set name for auto-captured user selections
        public const string NEXUS_LAST_SELECTION = "Nexus_Last_Selection";
        public const string NEXUS_PREFIX = "Nexus_";

        // Threshold for summary mode - above this, only return type counts
        // Rationale: Detailed info collection takes ~80ms per item (GetSelectedObject6 + geometry APIs)
        // At 30 items, detailed mode takes ~2.5s which is acceptable
        // At 500 items, it would take 40+ seconds which is unacceptable
        private const int SUMMARY_MODE_THRESHOLD = 30;

        public SelectionManager(Func<SolidWorksConnection> getConnection)
        {
            _getConnection = getConnection ?? throw new ArgumentNullException(nameof(getConnection));
        }

        /// <summary>
        /// Get information about all currently selected objects.
        /// Returns a dictionary with mode, total_count, and either selections (detailed) or summary (counts by type).
        /// </summary>
        public Dictionary<string, object> GetCurrentSelections()
        {
            var prof = new SimpleProfiler("GetCurrentSelections");

            if (!_getConnection().IsConnected)
                throw new InvalidOperationException("Not connected to SolidWorks");

            ISldWorks swApp = _getConnection().SwApp;
            ModelDoc2 doc = swApp.ActiveDoc as ModelDoc2;

            if (doc == null)
                throw new InvalidOperationException("No active document is open in SolidWorks");

            ISelectionMgr selMgr = (ISelectionMgr)doc.SelectionManager;
            int selCount = selMgr.GetSelectedObjectCount2(-1);
            prof.Mark($"init (count={selCount})");

            // Empty selection - return early
            if (selCount == 0)
            {
                prof.Done("no selections");
                return new Dictionary<string, object>
                {
                    ["mode"] = "detailed",
                    ["total_count"] = 0,
                    ["selections"] = new List<Dictionary<string, object>>()
                };
            }

            // Large selection - return summary mode (type counts only)
            if (selCount > SUMMARY_MODE_THRESHOLD)
            {
                return GetSelectionsSummaryMode(selMgr, selCount, prof);
            }

            // Normal selection - return detailed mode
            return GetSelectionsDetailedMode(doc, selMgr, selCount, prof);
        }

        /// <summary>
        /// Get selection summary for large selections - only type counts, no detailed info.
        /// This is fast because we only call GetSelectedObjectType3 (no GetSelectedObject6 or geometry APIs).
        /// </summary>
        private Dictionary<string, object> GetSelectionsSummaryMode(ISelectionMgr selMgr, int selCount, SimpleProfiler prof)
        {
            var typeCounts = new Dictionary<string, int>();

            for (int i = 1; i <= selCount; i++)
            {
                int typeCode = selMgr.GetSelectedObjectType3(i, -1);
                string typeName = GetFriendlyTypeName(typeCode);

                if (!typeCounts.ContainsKey(typeName))
                    typeCounts[typeName] = 0;
                typeCounts[typeName]++;
            }

            prof.Done($"summary mode - {selCount} items, {typeCounts.Count} types");

            return new Dictionary<string, object>
            {
                ["mode"] = "summary",
                ["total_count"] = selCount,
                ["summary"] = typeCounts,
                ["selections"] = new List<Dictionary<string, object>>()  // Empty in summary mode
            };
        }

        /// <summary>
        /// Get detailed selection info for normal-sized selections.
        /// </summary>
        private Dictionary<string, object> GetSelectionsDetailedMode(ModelDoc2 doc, ISelectionMgr selMgr, int selCount, SimpleProfiler prof)
        {
            var timers = new NamedTimers();
            var selections = new List<Dictionary<string, object>>();

            for (int i = 1; i <= selCount; i++)
            {
                var selInfo = GetSelectionInfo(doc, selMgr, i, timers);
                if (selInfo != null)
                {
                    selections.Add(selInfo);
                }
            }

            prof.Mark("loop done");

            // Log timing breakdown (useful for debugging)
            Console.WriteLine($"[PROFILE] GetCurrentSelections | GetSelectedObjectType3={timers.GetMs("GetSelectedObjectType3")}ms ({timers.GetCount("GetSelectedObjectType3")} calls)");
            Console.WriteLine($"[PROFILE] GetCurrentSelections | GetSelectedObject6={timers.GetMs("GetSelectedObject6")}ms ({timers.GetCount("GetSelectedObject6")} calls)");
            Console.WriteLine($"[PROFILE] GetCurrentSelections | GetSurface={timers.GetMs("GetSurface")}ms ({timers.GetCount("GetSurface")} calls)");
            Console.WriteLine($"[PROFILE] GetCurrentSelections | GetArea={timers.GetMs("GetArea")}ms ({timers.GetCount("GetArea")} calls)");
            Console.WriteLine($"[PROFILE] GetCurrentSelections | GetFeature={timers.GetMs("GetFeature")}ms ({timers.GetCount("GetFeature")} calls)");
            Console.WriteLine($"[PROFILE] GetCurrentSelections | GetBody={timers.GetMs("GetBody")}ms ({timers.GetCount("GetBody")} calls)");
            Console.WriteLine($"[PROFILE] GetCurrentSelections | GetCurve={timers.GetMs("GetCurve")}ms ({timers.GetCount("GetCurve")} calls)");
            Console.WriteLine($"[PROFILE] GetCurrentSelections | GetCurveParams2={timers.GetMs("GetCurveParams2")}ms ({timers.GetCount("GetCurveParams2")} calls)");
            Console.WriteLine($"[PROFILE] GetCurrentSelections | GetLength3={timers.GetMs("GetLength3")}ms ({timers.GetCount("GetLength3")} calls)");
            Console.WriteLine($"[PROFILE] GetCurrentSelections | GetTwoAdjacentFaces2={timers.GetMs("GetTwoAdjacentFaces2")}ms ({timers.GetCount("GetTwoAdjacentFaces2")} calls)");
            Console.WriteLine($"[PROFILE] GetCurrentSelections | GetPoint={timers.GetMs("GetPoint")}ms ({timers.GetCount("GetPoint")} calls)");
            Console.WriteLine($"[PROFILE] GetCurrentSelections | GetEdges={timers.GetMs("GetEdges")}ms ({timers.GetCount("GetEdges")} calls)");

            prof.Done($"detailed mode - returning {selections.Count} selections");

            return new Dictionary<string, object>
            {
                ["mode"] = "detailed",
                ["total_count"] = selCount,
                ["selections"] = selections
            };
        }

        /// <summary>
        /// Get a friendly type name from a selection type code.
        /// </summary>
        private string GetFriendlyTypeName(int typeCode)
        {
            switch ((swSelectType_e)typeCode)
            {
                case swSelectType_e.swSelFACES: return "Face";
                case swSelectType_e.swSelEDGES: return "Edge";
                case swSelectType_e.swSelVERTICES: return "Vertex";
                case swSelectType_e.swSelSKETCHSEGS:
                case swSelectType_e.swSelEXTSKETCHSEGS: return "SketchSegment";
                case swSelectType_e.swSelSKETCHPOINTS:
                case swSelectType_e.swSelEXTSKETCHPOINTS: return "SketchPoint";
                case swSelectType_e.swSelBODYFEATURES: return "Feature";
                case swSelectType_e.swSelSKETCHES: return "Sketch";
                case swSelectType_e.swSelDATUMPLANES: return "ReferencePlane";
                case swSelectType_e.swSelDATUMAXES: return "ReferenceAxis";
                case swSelectType_e.swSelCOMPONENTS: return "Component";
                case swSelectType_e.swSelSOLIDBODIES: return "SolidBody";
                case swSelectType_e.swSelSURFACEBODIES: return "SurfaceBody";
                case swSelectType_e.swSelDIMENSIONS: return "Dimension";
                default: return ((swSelectType_e)typeCode).ToString();
            }
        }

        /// <summary>
        /// Get information about a single selected object at the given index (1-based).
        /// </summary>
        private Dictionary<string, object> GetSelectionInfo(ModelDoc2 doc, ISelectionMgr selMgr, int index, NamedTimers timers)
        {
            try
            {
                Stopwatch sw;

                sw = Stopwatch.StartNew();
                int selType = selMgr.GetSelectedObjectType3(index, -1);
                sw.Stop();
                timers.AddTicks("GetSelectedObjectType3", sw.ElapsedTicks);

                sw = Stopwatch.StartNew();
                object selObj = selMgr.GetSelectedObject6(index, -1);
                sw.Stop();
                timers.AddTicks("GetSelectedObject6", sw.ElapsedTicks);

                if (selObj == null)
                    return null;

                var info = new Dictionary<string, object>
                {
                    ["index"] = index
                };

                switch ((swSelectType_e)selType)
                {
                    case swSelectType_e.swSelFACES:
                        return GetFaceSelectionInfo(info, selObj as IFace2, doc, timers);

                    case swSelectType_e.swSelEDGES:
                        return GetEdgeSelectionInfo(info, selObj as IEdge, doc, timers);

                    case swSelectType_e.swSelVERTICES:
                        return GetVertexSelectionInfo(info, selObj as IVertex, doc, timers);

                    // Sketch geometry (segments and points)
                    // swSelSKETCHSEGS = sketch in edit mode
                    // swSelEXTSKETCHSEGS = sketch NOT in edit mode (external)
                    case swSelectType_e.swSelSKETCHSEGS:
                    case swSelectType_e.swSelEXTSKETCHSEGS:
                        return GetSketchSegmentSelectionInfo(info, selObj as ISketchSegment);

                    // swSelSKETCHPOINTS = sketch in edit mode
                    // swSelEXTSKETCHPOINTS = sketch NOT in edit mode (external)
                    case swSelectType_e.swSelSKETCHPOINTS:
                    case swSelectType_e.swSelEXTSKETCHPOINTS:
                        return GetSketchPointSelectionInfo(info, selObj as ISketchPoint);

                    // All feature-like selections: regular features, sketches, ref planes, ref axes
                    case swSelectType_e.swSelBODYFEATURES:
                    case swSelectType_e.swSelSKETCHES:
                    case swSelectType_e.swSelSKETCHTEXT:
                    case swSelectType_e.swSelDATUMPLANES:
                    case swSelectType_e.swSelDATUMAXES:
                        return GetFeatureSelectionInfo(info, selObj as IFeature);

                    case swSelectType_e.swSelCOMPONENTS:
                        return GetComponentSelectionInfo(info, selObj as IComponent2);

                    case swSelectType_e.swSelSOLIDBODIES:
                    case swSelectType_e.swSelSURFACEBODIES:
                        return GetBodySelectionInfo(info, selObj as IBody2, selType);

                    case swSelectType_e.swSelDIMENSIONS:
                        return GetDimensionSelectionInfo(info, selObj as IDisplayDimension, doc);

                    default:
                        // For unknown types, return a generic selection
                        info["type"] = "Unknown";
                        info["sw_type"] = selType;
                        info["sw_type_name"] = ((swSelectType_e)selType).ToString();
                        info["description"] = $"Unknown selection type: {((swSelectType_e)selType).ToString()}";
                        return info;
                }
            }
            catch (Exception ex)
            {
                // Return error info if we can't process this selection
                return new Dictionary<string, object>
                {
                    ["index"] = index,
                    ["type"] = "Error",
                    ["error"] = ex.Message,
                    ["description"] = $"Error processing selection: {ex.Message}"
                };
            }
        }

        /// <summary>
        /// Get information about a selected face.
        /// </summary>
        private Dictionary<string, object> GetFaceSelectionInfo(Dictionary<string, object> info, IFace2 face, ModelDoc2 doc, NamedTimers timers)
        {
            if (face == null)
            {
                info["type"] = "Face";
                info["error"] = "Could not cast to IFace2";
                info["description"] = "Face (error reading properties)";
                return info;
            }

            info["type"] = "Face";
            Stopwatch sw;

            // Get surface type
            sw = Stopwatch.StartNew();
            ISurface surface = face.GetSurface() as ISurface;
            sw.Stop();
            timers.AddTicks("GetSurface", sw.ElapsedTicks);
            string surfaceType = GetSurfaceTypeName(surface);
            info["surface_type"] = surfaceType;

            // Get area (in mm²)
            sw = Stopwatch.StartNew();
            double area = face.GetArea() * 1e6; // Convert m² to mm²
            sw.Stop();
            timers.AddTicks("GetArea", sw.ElapsedTicks);
            info["area"] = Math.Round(area, 2);

            // Get parent feature
            sw = Stopwatch.StartNew();
            IFeature parentFeature = face.GetFeature() as IFeature;
            sw.Stop();
            timers.AddTicks("GetFeature", sw.ElapsedTicks);
            string parentFeatureName = parentFeature?.Name ?? "Unknown";
            info["parent_feature"] = parentFeatureName;

            // Get body name (for multi-body parts)
            sw = Stopwatch.StartNew();
            IBody2 body = face.GetBody() as IBody2;
            sw.Stop();
            timers.AddTicks("GetBody", sw.ElapsedTicks);
            string bodyName = GetBodyName(body);
            if (bodyName != null)
            {
                info["body_name"] = bodyName;
            }

            // Generate description
            string bodyPart = bodyName != null ? $" on body {bodyName}" : "";
            info["description"] = $"{surfaceType} face of {parentFeatureName}{bodyPart} ({info["area"]}mm²)";

            return info;
        }

        /// <summary>
        /// Get information about a selected edge.
        /// </summary>
        private Dictionary<string, object> GetEdgeSelectionInfo(Dictionary<string, object> info, IEdge edge, ModelDoc2 doc, NamedTimers timers)
        {
            if (edge == null)
            {
                info["type"] = "Edge";
                info["error"] = "Could not cast to IEdge";
                info["description"] = "Edge (error reading properties)";
                return info;
            }

            info["type"] = "Edge";
            Stopwatch sw;

            // Get curve type
            sw = Stopwatch.StartNew();
            ICurve curve = edge.GetCurve() as ICurve;
            sw.Stop();
            timers.AddTicks("GetCurve", sw.ElapsedTicks);
            string curveType = GetCurveTypeName(curve);
            info["curve_type"] = curveType;

            // Get length (in mm)
            try
            {
                ICurve edgeCurve = curve; // Reuse the curve we already got
                if (edgeCurve != null)
                {
                    // Use IEdge::GetCurveParams2 which returns an array
                    sw = Stopwatch.StartNew();
                    object paramsObj = edge.GetCurveParams2();
                    sw.Stop();
                    timers.AddTicks("GetCurveParams2", sw.ElapsedTicks);

                    if (paramsObj is double[] edgeParams && edgeParams.Length >= 8)
                    {
                        double startParam = edgeParams[6];
                        double endParam = edgeParams[7];

                        sw = Stopwatch.StartNew();
                        double length = edgeCurve.GetLength3(startParam, endParam) * 1000; // Convert m to mm
                        sw.Stop();
                        timers.AddTicks("GetLength3", sw.ElapsedTicks);

                        info["length"] = Math.Round(length, 2);
                    }
                }
            }
            catch
            {
                // Ignore errors getting edge length
            }

            // Get parent feature via adjacent face
            sw = Stopwatch.StartNew();
            IFace2[] faces = edge.GetTwoAdjacentFaces2() as IFace2[];
            sw.Stop();
            timers.AddTicks("GetTwoAdjacentFaces2", sw.ElapsedTicks);

            string parentFeatureName = "Unknown";
            if (faces != null && faces.Length > 0 && faces[0] != null)
            {
                sw = Stopwatch.StartNew();
                IFeature parentFeature = faces[0].GetFeature() as IFeature;
                sw.Stop();
                timers.AddTicks("GetFeature", sw.ElapsedTicks);
                parentFeatureName = parentFeature?.Name ?? "Unknown";
            }
            info["parent_feature"] = parentFeatureName;

            // Get body name
            sw = Stopwatch.StartNew();
            IBody2 body = edge.GetBody() as IBody2;
            sw.Stop();
            timers.AddTicks("GetBody", sw.ElapsedTicks);
            string bodyName = GetBodyName(body);
            if (bodyName != null)
            {
                info["body_name"] = bodyName;
            }

            // Generate description
            string lengthPart = info.ContainsKey("length") ? $" ({info["length"]}mm)" : "";
            info["description"] = $"{curveType} edge of {parentFeatureName}{lengthPart}";

            return info;
        }

        /// <summary>
        /// Get information about a selected vertex.
        /// </summary>
        private Dictionary<string, object> GetVertexSelectionInfo(Dictionary<string, object> info, IVertex vertex, ModelDoc2 doc, NamedTimers timers)
        {
            if (vertex == null)
            {
                info["type"] = "Vertex";
                info["error"] = "Could not cast to IVertex";
                info["description"] = "Vertex (error reading properties)";
                return info;
            }

            info["type"] = "Vertex";
            Stopwatch sw;

            // Get coordinates
            sw = Stopwatch.StartNew();
            double[] point = vertex.GetPoint() as double[];
            sw.Stop();
            timers.AddTicks("GetPoint", sw.ElapsedTicks);

            if (point != null && point.Length >= 3)
            {
                // Convert m to mm and round to 2 decimal places
                var coords = new double[]
                {
                    Math.Round(point[0] * 1000, 2),
                    Math.Round(point[1] * 1000, 2),
                    Math.Round(point[2] * 1000, 2)
                };
                info["coordinates"] = coords;
            }

            // Get body name
            sw = Stopwatch.StartNew();
            IEdge[] edges = vertex.GetEdges() as IEdge[];
            sw.Stop();
            timers.AddTicks("GetEdges", sw.ElapsedTicks);

            if (edges != null && edges.Length > 0 && edges[0] != null)
            {
                sw = Stopwatch.StartNew();
                IBody2 body = edges[0].GetBody() as IBody2;
                sw.Stop();
                timers.AddTicks("GetBody", sw.ElapsedTicks);
                string bodyName = GetBodyName(body);
                if (bodyName != null)
                {
                    info["body_name"] = bodyName;
                }
            }

            // Generate description
            if (info.ContainsKey("coordinates"))
            {
                var coords = info["coordinates"] as double[];
                info["description"] = $"Vertex at ({coords[0]}, {coords[1]}, {coords[2]})";
            }
            else
            {
                info["description"] = "Vertex (coordinates unavailable)";
            }

            return info;
        }

        /// <summary>
        /// Get information about a selected sketch segment (line, arc, spline, etc.).
        /// </summary>
        private Dictionary<string, object> GetSketchSegmentSelectionInfo(Dictionary<string, object> info, ISketchSegment segment)
        {
            info["type"] = "SketchSegment";

            if (segment == null)
            {
                info["error"] = "Could not cast to ISketchSegment";
                info["description"] = "Sketch segment (error reading properties)";
                return info;
            }

            // Get segment type
            int segType = segment.GetType();
            string segTypeName = GetSketchSegmentTypeName(segType);
            info["segment_type"] = segTypeName;

            // Get length if available
            try
            {
                double length = segment.GetLength() * 1000; // Convert m to mm
                info["length"] = Math.Round(length, 2);
            }
            catch
            {
                // Some segment types may not support GetLength
            }

            // Get parent sketch name
            ISketch sketch = segment.GetSketch();
            if (sketch != null)
            {
                IFeature sketchFeature = sketch as IFeature;
                if (sketchFeature != null)
                {
                    info["parent_sketch"] = sketchFeature.Name;
                }
            }

            // Check if construction geometry
            info["is_construction"] = segment.ConstructionGeometry;

            // Generate description
            string lengthPart = info.ContainsKey("length") ? $" ({info["length"]}mm)" : "";
            string sketchPart = info.ContainsKey("parent_sketch") ? $" in {info["parent_sketch"]}" : "";
            string constPart = segment.ConstructionGeometry ? " [construction]" : "";
            info["description"] = $"{segTypeName} sketch segment{lengthPart}{sketchPart}{constPart}";

            return info;
        }

        /// <summary>
        /// Get information about a selected sketch point.
        /// </summary>
        private Dictionary<string, object> GetSketchPointSelectionInfo(Dictionary<string, object> info, ISketchPoint sketchPoint)
        {
            info["type"] = "SketchPoint";

            if (sketchPoint == null)
            {
                info["error"] = "Could not cast to ISketchPoint";
                info["description"] = "Sketch point (error reading properties)";
                return info;
            }

            // Get coordinates (sketch points are in sketch coordinate system)
            double x = sketchPoint.X * 1000; // Convert m to mm
            double y = sketchPoint.Y * 1000;
            double z = sketchPoint.Z * 1000;
            info["coordinates"] = new double[] { Math.Round(x, 2), Math.Round(y, 2), Math.Round(z, 2) };

            // Get parent sketch name
            ISketch sketch = sketchPoint.GetSketch();
            if (sketch != null)
            {
                IFeature sketchFeature = sketch as IFeature;
                if (sketchFeature != null)
                {
                    info["parent_sketch"] = sketchFeature.Name;
                }
            }

            // Generate description
            var coords = info["coordinates"] as double[];
            string sketchPart = info.ContainsKey("parent_sketch") ? $" in {info["parent_sketch"]}" : "";
            info["description"] = $"Sketch point at ({coords[0]}, {coords[1]}, {coords[2]}){sketchPart}";

            return info;
        }

        /// <summary>
        /// Get information about a selected feature.
        /// All feature-like selections use this: regular features, sketches, ref planes, ref axes.
        /// The feature_type field distinguishes them (e.g., "ProfileFeature", "RefPlane", "RefAxis").
        /// </summary>
        private Dictionary<string, object> GetFeatureSelectionInfo(Dictionary<string, object> info, IFeature feature)
        {
            if (feature == null)
            {
                info["type"] = "Feature";
                info["error"] = "Could not cast to IFeature";
                info["description"] = "Feature (error reading properties)";
                return info;
            }

            string featureType = feature.GetTypeName2();
            string featureName = feature.Name;
            bool suppressed = feature.IsSuppressed();

            info["type"] = "Feature";
            info["name"] = featureName;
            info["feature_type"] = featureType;
            info["suppressed"] = suppressed;
            info["description"] = $"{featureName} ({featureType})";

            return info;
        }

        /// <summary>
        /// Get information about a selected component (assembly).
        /// </summary>
        private Dictionary<string, object> GetComponentSelectionInfo(Dictionary<string, object> info, IComponent2 component)
        {
            info["type"] = "Component";

            if (component == null)
            {
                info["error"] = "Could not cast to IComponent2";
                info["description"] = "Component (error reading properties)";
                return info;
            }

            info["name"] = component.Name2;

            // Get filename (just the filename, not full path)
            string pathName = component.GetPathName();
            if (!string.IsNullOrEmpty(pathName))
            {
                info["file_name"] = System.IO.Path.GetFileName(pathName);
            }

            // Get configuration
            string config = component.ReferencedConfiguration;
            if (!string.IsNullOrEmpty(config))
            {
                info["configuration"] = config;
            }

            // Generate description
            string fileName = info.ContainsKey("file_name") ? $" ({info["file_name"]})" : "";
            info["description"] = $"{info["name"]}{fileName}";

            return info;
        }

        /// <summary>
        /// Get information about a selected body.
        /// </summary>
        private Dictionary<string, object> GetBodySelectionInfo(Dictionary<string, object> info, IBody2 body, int selType)
        {
            info["type"] = "Body";

            if (body == null)
            {
                info["error"] = "Could not cast to IBody2";
                info["description"] = "Body (error reading properties)";
                return info;
            }

            // Determine body type
            string bodyType = (swSelectType_e)selType == swSelectType_e.swSelSOLIDBODIES ? "Solid" : "Surface";
            info["body_type"] = bodyType;

            // Get face count
            int faceCount = body.GetFaceCount();
            info["face_count"] = faceCount;

            // Get body name if available
            string bodyName = GetBodyName(body);
            if (bodyName != null)
            {
                info["name"] = bodyName;
                info["description"] = $"{bodyName} ({bodyType}, {faceCount} faces)";
            }
            else
            {
                info["description"] = $"{bodyType} body ({faceCount} faces)";
            }

            return info;
        }

        /// <summary>
        /// Get information about a selected dimension.
        /// </summary>
        private Dictionary<string, object> GetDimensionSelectionInfo(Dictionary<string, object> info, IDisplayDimension dispDim, ModelDoc2 doc)
        {
            info["type"] = "Dimension";

            if (dispDim == null)
            {
                info["error"] = "Could not cast to IDisplayDimension";
                info["description"] = "Dimension (error reading properties)";
                return info;
            }

            IDimension dim = dispDim.GetDimension2(0);
            if (dim != null)
            {
                info["name"] = dim.FullName;
                double value = dim.Value;

                // Determine unit based on dimension type
                int dimType = dispDim.Type2;
                bool isAngular = dimType == (int)swDimensionType_e.swAngularDimension;

                if (isAngular)
                {
                    // Convert radians to degrees
                    value = value * 180.0 / Math.PI;
                    info["value"] = Math.Round(value, 2);
                    info["unit"] = "deg";
                    info["description"] = $"{info["name"]} = {info["value"]}deg";
                }
                else
                {
                    // Convert m to mm
                    value = value * 1000;
                    info["value"] = Math.Round(value, 2);
                    info["unit"] = "mm";
                    info["description"] = $"{info["name"]} = {info["value"]}mm";
                }
            }
            else
            {
                info["description"] = "Dimension (could not read value)";
            }

            return info;
        }

        // =====================================================================
        // Selection Set Operations
        // =====================================================================

        /// <summary>
        /// Save the current selection to a selection set named "Nexus_Last_Selection".
        /// If a selection set with that name already exists, it is deleted first.
        /// If nothing is selected, any existing Nexus_Last_Selection is deleted.
        /// </summary>
        public void SaveCurrentSelectionToNexusLastSelection()
        {
            if (!_getConnection().IsConnected)
                throw new InvalidOperationException("Not connected to SolidWorks");

            ISldWorks swApp = _getConnection().SwApp;
            ModelDoc2 doc = swApp.ActiveDoc as ModelDoc2;

            if (doc == null)
                throw new InvalidOperationException("No active document is open in SolidWorks");

            IModelDocExtension ext = doc.Extension;
            ISelectionMgr selMgr = (ISelectionMgr)doc.SelectionManager;
            IFeatureManager featMgr = doc.FeatureManager;

            // Check if anything is selected BEFORE deleting existing Nexus_Last_Selection.
            // If nothing is selected, we preserve the existing selection to maintain UX continuity
            // (e.g., agent asks a question, user replies without selecting anything, agent can still
            // access the original selection the user made).
            int selCount = selMgr.GetSelectedObjectCount2(-1);
            if (selCount == 0)
            {
                Console.WriteLine("[INFO] No selection to save, preserving existing Nexus_Last_Selection");
                return;
            }

            // Get the selection set folder
            ISelectionSetFolder selSetFolder = (ISelectionSetFolder)featMgr.GetSelectionSetFolder();
            if (selSetFolder == null)
            {
                Console.WriteLine("[WARN] Could not get SelectionSetFolder");
                return;
            }

            // IMPORTANT: When running inside PerformanceOptimizationScope, the feature tree
            // may be disabled (EnableFeatureTree = false). We need to temporarily re-enable it
            // so that SaveSelection() updates the feature tree and FeatureByName() can find
            // the newly created selection set.
            bool wasFeatureTreeEnabled = featMgr.EnableFeatureTree;

            try
            {
                // Temporarily enable feature tree updates
                featMgr.EnableFeatureTree = true;

                // Save the current selection FIRST (creates a new selection set with auto-generated name).
                // We must do this BEFORE deleting the old Nexus_Last_Selection because
                // RemoveSelectionSet() can clear the current selection as a side effect.
                int status;
                object result = ext.SaveSelection(out status);

                if (status != 1 || result == null)
                {
                    Console.WriteLine($"[WARN] SaveSelection failed with status={status}");
                    return;
                }

                ISelectionSet newSelSet = (ISelectionSet)result;
                string autoName = newSelSet.GetName();

                // Get the feature for this selection set so we can rename it
                IFeature feat = GetFeatureByName(doc, autoName);
                if (feat == null)
                {
                    Console.WriteLine($"[WARN] Could not find feature for selection set '{autoName}'");
                    return;
                }

                // NOW delete the old Nexus_Last_Selection (after we've saved the new one)
                DeleteSelectionSetByName(selSetFolder, NEXUS_LAST_SELECTION);

                // Rename the new selection set to NEXUS_LAST_SELECTION
                feat.Name = NEXUS_LAST_SELECTION;

                Console.WriteLine($"[INFO] Saved selection to '{NEXUS_LAST_SELECTION}' (was '{autoName}')");
            }
            finally
            {
                // Restore feature tree state
                featMgr.EnableFeatureTree = wasFeatureTreeEnabled;
            }
        }

        /// <summary>
        /// Delete a selection set by name if it exists.
        /// </summary>
        private void DeleteSelectionSetByName(ISelectionSetFolder folder, string name)
        {
            object selSetsObj = folder.GetSelectionSets();
            if (selSetsObj == null)
                return;

            object[] selSets = selSetsObj as object[];
            if (selSets == null)
                return;

            foreach (object setObj in selSets)
            {
                ISelectionSet selSet = setObj as ISelectionSet;
                if (selSet != null && selSet.GetName() == name)
                {
                    selSet.RemoveSelectionSet();
                    Console.WriteLine($"[INFO] Deleted existing selection set '{name}'");
                    return;
                }
            }
        }

        /// <summary>
        /// Get a feature by name from the document.
        /// Works with Part, Assembly, and Drawing documents.
        /// </summary>
        private IFeature GetFeatureByName(ModelDoc2 doc, string name)
        {
            // Try PartDoc
            IPartDoc partDoc = doc as IPartDoc;
            if (partDoc != null)
            {
                return partDoc.FeatureByName(name) as IFeature;
            }

            // Try AssemblyDoc
            IAssemblyDoc assyDoc = doc as IAssemblyDoc;
            if (assyDoc != null)
            {
                return assyDoc.FeatureByName(name) as IFeature;
            }

            // Try DrawingDoc
            IDrawingDoc drawDoc = doc as IDrawingDoc;
            if (drawDoc != null)
            {
                return drawDoc.FeatureByName(name) as IFeature;
            }

            return null;
        }

        // =====================================================================
        // Helper Methods
        // =====================================================================

        /// <summary>
        /// Get the name of a body (from its feature).
        /// Returns null if body has no name.
        /// </summary>
        private string GetBodyName(IBody2 body)
        {
            if (body == null)
                return null;

            try
            {
                // Try to get the body's name via its feature
                string name = body.Name;
                if (!string.IsNullOrEmpty(name))
                {
                    return name;
                }
            }
            catch
            {
                // Ignore errors getting body name
            }

            return null;
        }

        /// <summary>
        /// Get a human-readable name for a surface type.
        /// </summary>
        private string GetSurfaceTypeName(ISurface surface)
        {
            if (surface == null)
                return "Unknown";

            try
            {
                // IsSphere, IsCylinder, etc. methods
                if (surface.IsPlane())
                    return "Planar";
                if (surface.IsCylinder())
                    return "Cylindrical";
                if (surface.IsCone())
                    return "Conical";
                if (surface.IsSphere())
                    return "Spherical";
                if (surface.IsTorus())
                    return "Toroidal";

                // Default to spline/NURBS for complex surfaces
                return "Spline";
            }
            catch
            {
                return "Unknown";
            }
        }

        /// <summary>
        /// Get a human-readable name for a curve type.
        /// </summary>
        private string GetCurveTypeName(ICurve curve)
        {
            if (curve == null)
                return "Unknown";

            try
            {
                if (curve.IsLine())
                    return "Linear";
                if (curve.IsCircle())
                    return "Circular";
                if (curve.IsEllipse())
                    return "Elliptical";

                // Default to spline for complex curves
                return "Spline";
            }
            catch
            {
                return "Unknown";
            }
        }

        /// <summary>
        /// Get a human-readable name for a sketch segment type.
        /// </summary>
        private string GetSketchSegmentTypeName(int segType)
        {
            // Strip "swSketch" prefix from enum name for cleaner output
            string enumName = ((swSketchSegments_e)segType).ToString();
            return enumName.StartsWith("swSketch") ? enumName.Substring(8) : enumName;
        }
    }
}
