using System;
using System.Collections.Generic;
using System.Globalization;
using SolidWorks.Interop.sldworks;

namespace CosmonSWService
{
    /// <summary>
    /// Extracts the state of the active drawing document as a Sheet -> View ->
    /// {Dimension, Annotation, Table} hierarchy. Mirrors the read logic of the
    /// get_drawing_layout_info helper and generalises it to all sheets plus view
    /// types, dimensions, annotations and (best-effort) tables.
    ///
    /// Version-agnostic and fail-soft: only long-standing API methods are used,
    /// type codes are compared as ints (no enum members that may be absent on
    /// older interops), and every optional read is guarded so a property or method
    /// missing on a given SolidWorks version degrades to partial data rather than
    /// failing the whole walk. The result dict mirrors the Python DrawingStateResult.
    ///
    /// Conventions (SolidWorks internal units): sheet coordinates are in METERS in the
    /// API and converted to MILLIMETRES here (x1000). The sheet origin is the bottom-left
    /// corner. View.Position is the view CENTRE; View.GetOutline() is the geometry
    /// bounding box {xMin,yMin,xMax,yMax} (excludes dims/annotations). A dimension's text
    /// position comes from its Annotation.GetPosition(), not the Dimension; GetDimension2(0)
    /// is the primary dimension. DrawingDoc.GetViews() returns a jagged [sheet][views...]
    /// array; the first view of each group (Type == 1) is the sheet itself and is skipped.
    /// </summary>
    public class DrawingStateManager
    {
        private readonly Func<SolidWorksConnection> _getConnection;

        public DrawingStateManager(Func<SolidWorksConnection> getConnection)
        {
            _getConnection = getConnection ?? throw new ArgumentNullException(nameof(getConnection));
        }

        /// <summary>
        /// Get the current drawing state.
        /// </summary>
        /// <exception cref="InvalidOperationException">Not connected, no document, or not a drawing.</exception>
        public Dictionary<string, object> GetDrawingState()
        {
            if (!_getConnection().IsConnected)
                throw new InvalidOperationException("Not connected to SolidWorks");

            ISldWorks swApp = _getConnection().SwApp;
            ModelDoc2 doc = swApp.ActiveDoc as ModelDoc2;
            if (doc == null)
                throw new InvalidOperationException("No active document is open in SolidWorks");

            IDrawingDoc drawDoc = doc as IDrawingDoc;
            if (drawDoc == null)
                throw new InvalidOperationException("Active document is not a drawing");

            var result = new Dictionary<string, object>();
            result["document_title"] = doc.GetTitle();
            // Full path of the active document; empty string for an unsaved document.
            // Emitted as "document_path" so the agent can key per-document model
            // state and never diff one document's drawing state against another's.
            result["document_path"] = doc.GetPathName();

            using (new PerformanceOptimizationScope(swApp, doc))
            {
                result["sheets"] = ExtractSheets(doc, drawDoc);
            }

            return result;
        }

        private static List<Dictionary<string, object>> ExtractSheets(ModelDoc2 doc, IDrawingDoc drawDoc)
        {
            var sheets = new List<Dictionary<string, object>>();

            // Document linear unit (swUserPreferenceIntegerValue_e.swUnitsLinear == 47) — a
            // swLengthUnit_e code used to render dimension values in the drawing's display units.
            int linearUnit = SafeInt(() => doc.GetUserPreferenceIntegerValue(47));

            // Properties of the current sheet (other sheets would need activation to read,
            // which we avoid; their paper/scale/size are left null).
            string currentSheetName = null;
            double[] currentSheetProps = null;
            try
            {
                ISheet current = drawDoc.GetCurrentSheet() as ISheet;
                if (current != null)
                {
                    currentSheetName = current.GetName();
                    currentSheetProps = current.GetProperties2() as double[];
                }
            }
            catch { }

            // DrawingDoc.GetViews() returns a JAGGED array: one entry per sheet, each a
            // [sheetView, view1, view2, ...] array. The first element (Type == 1) is the
            // sheet itself; the rest are the real drawing views on that sheet.
            object[] sheetGroups = null;
            try { sheetGroups = drawDoc.GetViews() as object[]; }
            catch { }
            if (sheetGroups == null)
                return sheets;

            foreach (object groupObj in sheetGroups)
            {
                object[] viewsInSheet = groupObj as object[];
                if (viewsInSheet == null)
                    continue;

                string sheetName = null;
                var builtViews = new List<Dictionary<string, object>>();
                foreach (object vObj in viewsInSheet)
                {
                    try
                    {
                        IView v = vObj as IView;
                        if (v == null)
                            continue;
                        if (SafeInt(() => v.Type) == 1)   // the sheet itself — skip
                        {
                            sheetName = SafeName(v);
                            continue;
                        }
                        builtViews.Add(BuildView(v, linearUnit));
                    }
                    catch { }
                }

                var sheet = BuildSheet(sheetName, currentSheetName, currentSheetProps);
                ((List<Dictionary<string, object>>)sheet["views"]).AddRange(builtViews);
                sheets.Add(sheet);
            }

            // Best-effort tables (reading tables is not well-supported across versions):
            // attach any discovered table features to the first sheet.
            if (sheets.Count > 0)
            {
                var tables = ExtractTables(doc);
                if (tables.Count > 0)
                    ((List<Dictionary<string, object>>)sheets[0]["tables"]).AddRange(tables);
            }

            return sheets;
        }

        private static Dictionary<string, object> BuildSheet(
            string name, string currentSheetName, double[] currentProps)
        {
            var sheet = new Dictionary<string, object>();
            sheet["name"] = name ?? "(unnamed sheet)";
            sheet["views"] = new List<Dictionary<string, object>>();
            sheet["tables"] = new List<Dictionary<string, object>>();

            // Sheet properties are only available for the active sheet (see ExtractSheets).
            if (name != null && name == currentSheetName
                && currentProps != null && currentProps.Length >= 8)
            {
                string paper = MapPaperSize((int)currentProps[0]);
                if (paper != null) sheet["paper_size"] = paper;
                if (currentProps[3] != 0)
                    sheet["scale"] = FormatRatio(currentProps[2], currentProps[3]);
                sheet["width_mm"] = currentProps[5] * 1000.0;
                sheet["height_mm"] = currentProps[6] * 1000.0;
            }

            return sheet;
        }

        private static Dictionary<string, object> BuildView(IView view, int linearUnit)
        {
            var v = new Dictionary<string, object>();
            v["name"] = SafeName(view) ?? "(unnamed view)";
            v["view_type"] = MapViewType(SafeInt(() => view.Type));

            try
            {
                double scale = view.ScaleDecimal;
                if (scale > 0) v["scale"] = FormatScale(scale);
            }
            catch { }

            try
            {
                string cfg = view.ReferencedConfiguration;
                if (!string.IsNullOrEmpty(cfg)) v["reference_configuration"] = cfg;
            }
            catch { }

            try
            {
                ModelDoc2 refModel = view.ReferencedDocument as ModelDoc2;
                string title = refModel?.GetTitle();
                if (!string.IsNullOrEmpty(title)) v["reference_document"] = title;
            }
            catch { }

            try
            {
                // View.Position is the view CENTRE in sheet coords (m, origin bottom-left).
                double[] pos = view.Position as double[];
                if (pos != null && pos.Length >= 2)
                    v["position"] = new double[] { pos[0] * 1000.0, pos[1] * 1000.0 };  // -> mm
            }
            catch { }

            try
            {
                // GetOutline() = geometry bbox {xMin,yMin,xMax,yMax} (excludes dims/annotations).
                double[] outline = view.GetOutline() as double[];
                if (outline != null && outline.Length >= 4)
                    v["size"] = new double[]
                    {
                        (outline[2] - outline[0]) * 1000.0,  // width -> mm
                        (outline[3] - outline[1]) * 1000.0,  // height -> mm
                    };
            }
            catch { }

            v["dimensions"] = ExtractDimensions(view, linearUnit);
            v["annotations"] = ExtractAnnotations(view);
            v["tables"] = new List<Dictionary<string, object>>();

            return v;
        }

        private static List<Dictionary<string, object>> ExtractDimensions(IView view, int linearUnit)
        {
            var dims = new List<Dictionary<string, object>>();
            try
            {
                IDisplayDimension dd = view.GetFirstDisplayDimension5() as IDisplayDimension;
                while (dd != null)
                {
                    var d = new Dictionary<string, object>();

                    string type = MapDimensionType(SafeInt(() => (int)dd.Type2));
                    if (type != null) d["type"] = type;

                    IDimension dim = null;
                    try { dim = dd.GetDimension2(0) as IDimension; } catch { }

                    string name = null;
                    if (dim != null)
                    {
                        try { name = dim.FullName; } catch { }
                        if (string.IsNullOrEmpty(name)) { try { name = dim.Name; } catch { } }

                        // SystemValue is SI (metres for linear, radians for angular); render it
                        // in the document's display units. GetType()==1 marks an angular param.
                        bool angular = SafeInt(() => dim.GetType()) == 1;
                        try { d["value"] = FormatMeasure(dim.SystemValue, angular, linearUnit); }
                        catch { }

                        string tolerance = ExtractTolerance(dim, angular, linearUnit);
                        if (tolerance != null) d["tolerance"] = tolerance;
                    }
                    d["name"] = string.IsNullOrEmpty(name) ? "(unnamed)" : name;

                    try
                    {
                        // Dim text position comes from the Annotation, not the Dimension.
                        // Sheet coords (m, origin bottom-left) -> mm. Some dims store none.
                        IAnnotation ann = dd.GetAnnotation() as IAnnotation;
                        double[] pos = ann?.GetPosition() as double[];
                        if (pos != null && pos.Length >= 2)
                            d["position"] = new double[] { pos[0] * 1000.0, pos[1] * 1000.0 };
                    }
                    catch { }

                    dims.Add(d);
                    dd = dd.GetNext5() as IDisplayDimension;
                }
            }
            catch { }
            return dims;
        }

        private static List<Dictionary<string, object>> ExtractAnnotations(IView view)
        {
            var anns = new List<Dictionary<string, object>>();
            try
            {
                IAnnotation a = view.GetFirstAnnotation3() as IAnnotation;
                while (a != null)
                {
                    int typeCode = SafeInt(() => a.GetType());

                    // swAnnotationType_e: 4 == DisplayDimension, captured separately above.
                    if (typeCode != 4)
                    {
                        var ad = new Dictionary<string, object>();
                        ad["type"] = MapAnnotationType(typeCode);

                        if (typeCode == 6) // Note
                        {
                            try
                            {
                                Note note = a.GetSpecificAnnotation() as Note;
                                string text = note?.GetText();
                                if (!string.IsNullOrEmpty(text)) ad["text"] = text;
                            }
                            catch { }
                        }

                        try
                        {
                            // Sheet coords (m, origin bottom-left) -> mm.
                            double[] pos = a.GetPosition() as double[];
                            if (pos != null && pos.Length >= 2)
                                ad["position"] = new double[] { pos[0] * 1000.0, pos[1] * 1000.0 };
                        }
                        catch { }

                        anns.Add(ad);
                    }

                    a = a.GetNext3() as IAnnotation;
                }
            }
            catch { }
            return anns;
        }

        private static List<Dictionary<string, object>> ExtractTables(ModelDoc2 doc)
        {
            var tables = new List<Dictionary<string, object>>();
            try
            {
                Feature feat = doc.FirstFeature() as Feature;
                int guard = 0;
                while (feat != null && guard++ < 5000)
                {
                    string typeName = null;
                    try { typeName = feat.GetTypeName2(); } catch { }

                    if (typeName != null && IsTableFeature(typeName))
                    {
                        var t = new Dictionary<string, object>();
                        t["type"] = typeName;
                        try
                        {
                            string title = feat.Name;
                            if (!string.IsNullOrEmpty(title)) t["title"] = title;
                        }
                        catch { }
                        tables.Add(t);
                    }

                    Feature next = null;
                    try { next = feat.GetNextFeature() as Feature; } catch { break; }
                    feat = next;
                }
            }
            catch { }
            return tables;
        }

        private static bool IsTableFeature(string typeName)
        {
            string t = typeName.ToLowerInvariant();
            return t.Contains("bom") || t.Contains("table") || t.Contains("weldmentcutlist")
                || t.Contains("revision");
        }

        // ------------------------------------------------------------------
        // Helpers
        // ------------------------------------------------------------------

        private static string SafeName(IView view)
        {
            try { return view.GetName2(); }
            catch { return null; }
        }

        private static int SafeInt(Func<int> read)
        {
            try { return read(); }
            catch { return -1; }
        }

        private static string FormatRatio(double num, double den)
        {
            return num.ToString("0.##", CultureInfo.InvariantCulture)
                + ":" + den.ToString("0.##", CultureInfo.InvariantCulture);
        }

        private static string FormatScale(double scale)
        {
            if (scale >= 1.0)
                return scale.ToString("0.##", CultureInfo.InvariantCulture) + ":1";
            return "1:" + (1.0 / scale).ToString("0.##", CultureInfo.InvariantCulture);
        }

        // swDimensionType_e (Type2): only types observed on real drawings are mapped;
        // any other code leaves the dimension type unset.
        private static string MapDimensionType(int code)
        {
            switch (code)
            {
                case 2: return "Linear";
                case 3: return "Angular";
                case 6: return "Diameter";
                default: return null;
            }
        }

        // Render an SI measurement (metres, or radians when angular) in the document's
        // display units. Falls back to metres for unmapped linear units.
        private static string FormatMeasure(double si, bool angular, int linearUnit)
        {
            if (angular)
                return FormatNum(si * 180.0 / Math.PI) + "°";
            double factor;
            string suffix;
            if (TryLinearUnit(linearUnit, out factor, out suffix))
                return FormatNum(si * factor) + suffix;
            return FormatNum(si) + "m";
        }

        private static string FormatNum(double v)
        {
            return v.ToString("0.####", CultureInfo.InvariantCulture);
        }

        // swLengthUnit_e -> (metres->unit factor, suffix). Covers the common units;
        // unmapped units fall back to metres in FormatMeasure.
        private static bool TryLinearUnit(int code, out double factor, out string suffix)
        {
            switch (code)
            {
                case 0: factor = 1000.0; suffix = "mm"; return true;
                case 1: factor = 100.0; suffix = "cm"; return true;
                case 2: factor = 1.0; suffix = "m"; return true;
                case 3: factor = 1.0 / 0.0254; suffix = "in"; return true;
                case 4: factor = 1.0 / 0.3048; suffix = "ft"; return true;
                default: factor = 1.0; suffix = null; return false;
            }
        }

        // Tolerance string from IDimensionTolerance. Only the types observed on real
        // drawings are rendered (swTolNONE -> none, swTolSYMMETRIC -> ±value); other
        // tolerance types leave the field unset pending a live sighting.
        private static string ExtractTolerance(IDimension dim, bool angular, int linearUnit)
        {
            try
            {
                IDimensionTolerance tol = dim.Tolerance as IDimensionTolerance;
                if (tol == null)
                    return null;
                int tolType = SafeInt(() => (int)tol.Type);
                if (tolType == 4) // swTolSYMMETRIC
                {
                    double max = tol.GetMaxValue();
                    if (max != 0)
                        return "±" + FormatMeasure(max, angular, linearUnit);
                }
            }
            catch { }
            return null;
        }

        // swDwgPaperSizes_e (stable across versions). Returns null for unknown codes.
        private static string MapPaperSize(int code)
        {
            switch (code)
            {
                case 0: return "A";
                case 1: return "A-vertical";
                case 2: return "B";
                case 3: return "C";
                case 4: return "D";
                case 5: return "E";
                case 6: return "A4";
                case 7: return "A4-vertical";
                case 8: return "A3";
                case 9: return "A2";
                case 10: return "A1";
                case 11: return "A0";
                case 12: return "Custom";
                default: return null;
            }
        }

        // swDrawingViewTypes_e (best-effort labels; falls back to the raw code).
        private static string MapViewType(int code)
        {
            switch (code)
            {
                case 1: return "Sheet";
                case 2: return "Named View";
                case 3: return "Detail";
                case 4: return "Section";
                case 5: return "Detached";
                case 6: return "Projected";
                case 7: return "Auxiliary";
                default: return "ViewType" + code;
            }
        }

        // swAnnotationType_e (subset; falls back to the raw code). Only codes seen on
        // real drawings are mapped; cosmetic threads (1) and surface-finish symbols (7)
        // are common on machined-part drawings.
        private static string MapAnnotationType(int code)
        {
            switch (code)
            {
                case 1: return "CosmeticThread";
                case 2: return "DatumTag";
                case 5: return "Gtol";
                case 6: return "Note";
                case 7: return "SurfaceFinish";
                case 13: return "CenterMark";
                default: return "Annotation" + code;
            }
        }
    }
}
