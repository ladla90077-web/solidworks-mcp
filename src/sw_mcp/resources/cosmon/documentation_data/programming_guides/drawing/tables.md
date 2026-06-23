---
description: Drawing tables API for SolidWorks — BOM, hole, revision, bend, weldment cut list, and general tables. Prefer the General table (ITableAnnotation via InsertTableAnnotation2) over specialized types; it is more flexible and reliable. Covers the shared ITableAnnotation base (sizing, row/column ops, positioning, splitting, formatting), per-type insertion, anchors, and iteration.
---
# Agent Guide: Creating & Managing Tables in SolidWorks Drawings

You are writing C# code that runs inside a SolidWorks add-in or macro to create/modify tables on drawing sheets. This guide tells you what to do and where to look up details.

## Documentation Available to You

You have the full SolidWorks API docs in `sldworksapi/` and constants in `swconst/`. Key files:

**Search patterns to find what you need:**
- Interface docs: `sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.I<InterfaceName>.md`
- Members list: same path but with `_members.md` suffix
- Methods: same path with `~MethodName.md` suffix
- Constants: `swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.<EnumName>.md`
- Code examples: `sldworksapi/Insert_BOM_Table_Example_CSharp.md`, `Insert_Hole_Table_Example_CSharp.md`, etc.

**Key interfaces to search for:**
- `ITableAnnotation` - base for all drawing tables (sizing, positioning, rows, columns, formatting)
- `IBomTableAnnotation` / `IBomFeature` - BOM tables
- `IHoleTableAnnotation` / `IHoleTable` - Hole tables
- `IRevisionTableAnnotation` / `IRevisionTableFeature` - Revision tables
- `IBendTableAnnotation` / `IBendTable` - Bend tables
- `IWeldmentCutListAnnotation` / `IWeldmentCutListFeature` - Weldment cut lists
- `IGeneralTableFeature` - General tables
- `IDesignTable` - Design tables (Excel-based, NOT ITableAnnotation)

**Reference guide with C# examples:** `guides/drawing-tables-comprehensive-guide.md`

---

## Decision Tree: Which Table to Insert

1. **Assembly parts list** → BOM Table via `IView.InsertBomTable4/5/6`
2. **Hole locations** → Hole Table via `IView.InsertHoleTable3` (pre-select datum + holes)
3. **Drawing revision history** → Revision Table via `ISheet.InsertRevisionTable2`
4. **Sheet metal bend data** → Bend Table via `IView.InsertBendTable`
5. **Weldment body list** → Weldment Cut List via `IView.InsertWeldmentTable`
6. **Custom/arbitrary data** → General Table via `IDrawingDoc.InsertTableAnnotation2`
7. **Configuration parameters** → Design Table (`IDesignTable`) - embedded Excel, different API

---

## Step-by-Step: Inserting Any Table

### 1. Get the drawing and view

```csharp
ModelDoc2 swModel = (ModelDoc2)swApp.ActiveDoc;
DrawingDoc swDraw = (DrawingDoc)swModel;
ModelDocExtension ext = swModel.Extension;

// Select the target view (needed for BOM, Hole, Bend, Weldment tables)
ext.SelectByID2(viewName, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
View swView = (View)swModel.SelectionManager.GetSelectedObject6(1, 0);
```

### 2. Choose positioning strategy

**Option A: Anchor point (recommended)** — Set `UseAnchorPoint = true`. The table snaps to the anchor defined in the sheet format. The anchor corner stays fixed as rows are added/removed.

**Option B: Absolute coordinates** — Set `UseAnchorPoint = false` and provide X, Y in meters. Use this when there's no anchor or you need a specific position.

### 3. Insert the table

All insertion methods follow the same pattern:
```
result = target.InsertXxxTable(UseAnchorPoint, X, Y, AnchorType, ...type-specific params..., TemplatePath)
```

- `AnchorType`: use `swBOMConfigurationAnchorType_e` (TopLeft=0, TopRight=1, BottomLeft=2, BottomRight=3)
- `TemplatePath`: empty string `""` for default template, or full path to `.sldXXXtbt` file
- Return value is the table annotation object (or null on failure)

**Always null-check the return value.** Common failure causes:
- No view selected (for view-based tables)
- View doesn't contain the right model type (e.g., BOM needs an assembly)
- For hole tables: forgot to pre-select datum origin and hole edges
- Template path doesn't exist

### 4. Configure after insertion

Cast to `TableAnnotation` for sizing/formatting:
```csharp
TableAnnotation tableAnn = (TableAnnotation)bomAnn;  // or whatever table type
```

Then use `ITableAnnotation` methods for:
- **Sizing**: `SetColumnWidth(col, meters)`, `SetRowHeight(row, meters)`
- **Position**: `((Annotation)tableAnn.GetAnnotation()).SetPosition2(x, y, 0)`
- **Anchor**: `tableAnn.Anchored = true; tableAnn.AnchorType = ...`
- **Content**: `tableAnn.Text2[row, col] = "value"`
- **Rows**: `tableAnn.InsertRow(pos, after)`, `tableAnn.DeleteRow2(row, true)`
- **Split**: `tableAnn.HorizontalAutoSplit(maxRows, 1, 0)` for auto-split

---

## Handling Common Problems

### Table doesn't fit on sheet

```csharp
// 1. Try reducing column widths
for (int i = 0; i < tableAnn.ColumnCount; i++)
    tableAnn.SetColumnWidth(i, 0.025); // 25mm

// 2. Try auto-split (splits into sections when rows exceed max)
if (tableAnn.RowCount > 20)
    tableAnn.HorizontalAutoSplit(20, 1, 0); // 20 rows max, continuous, below
```

### Multiple tables overlapping

Calculate the extent of the first table and offset the second:
```csharp
double totalHeight = 0;
for (int i = 0; i < table1.RowCount; i++)
    totalHeight += table1.GetRowHeight(i);

double totalWidth = 0;
for (int i = 0; i < table1.ColumnCount; i++)
    totalWidth += table1.GetColumnWidth(i);

// Position table2 below table1 with 10mm gap
Annotation ann1 = (Annotation)table1.GetAnnotation();
double[] pos = (double[])ann1.GetPosition();
Annotation ann2 = (Annotation)table2.GetAnnotation();
ann2.SetPosition2(pos[0], pos[1] - totalHeight - 0.01, 0);
```

### Position drifts when rows change

Use anchoring. The anchor corner stays fixed:
```csharp
tableAnn.Anchored = true;
tableAnn.AnchorType = (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_TopRight;
// TopRight anchor: table grows down-left, top-right corner is fixed
```

### Row deletion index shift

Always delete bottom-to-top:
```csharp
for (int i = tableAnn.RowCount - 1; i >= 1; i--)
    if (shouldDelete(i)) tableAnn.DeleteRow2(i, true);
```

---

## Quick Insertion Recipes

### BOM Table
```csharp
BomTableAnnotation bomAnn = swView.InsertBomTable4(
    true, 0, 0,
    (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_TopRight,
    (int)swBomType_e.swBomType_TopLevelOnly,
    "", "", false, 0, false);
```
Search docs: `sldworksapi/*IView~InsertBomTable4*` through `InsertBomTable6`

### Revision Table
```csharp
Sheet sheet = (Sheet)swDraw.GetCurrentSheet();
RevisionTableAnnotation revAnn = (RevisionTableAnnotation)sheet.InsertRevisionTable2(
    true, 0, 0,
    (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_TopRight,
    "", (int)swRevisionTableSymbolShape_e.swRevisionTable_CircleSymbol, true);
```
Search docs: `sldworksapi/*ISheet~InsertRevisionTable*`

### Hole Table
```csharp
// PRE-SELECT: datum vertex (mark=1), hole edges (mark=2) before calling
object holeAnn = swView.InsertHoleTable3(
    true, 0, 0,
    (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_BottomLeft,
    "A", "",
    (int)swHoleTableTagOrder_e.swHoleTableTagOrder_LeftToRight,
    (int)swHoleTableTagStyle_e.swHoleTable_Letters, null);
```
Search docs: `sldworksapi/*IView~InsertHoleTable3*`

### Bend Table
```csharp
BendTableAnnotation bendAnn = (BendTableAnnotation)swView.InsertBendTable(
    true, 0, 0,
    (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_TopLeft,
    "A", "");
```
Search docs: `sldworksapi/*IView~InsertBendTable*`

### Weldment Cut List
```csharp
object weldAnn = swView.InsertWeldmentTable(
    true, 0, 0,
    (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_BottomLeft, "");
```
Search docs: `sldworksapi/*IView~InsertWeldmentTable*`

### General Table
```csharp
TableAnnotation tableAnn = (TableAnnotation)swDraw.InsertTableAnnotation2(
    0.1, 0.2,
    (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_TopLeft,
    3, 5, ""); // 3 cols, 5 rows
```
Search docs: `sldworksapi/*InsertTableAnnotation2*`

---

## Where to Find More

When you need details on a specific method or property, search the docs:

| What you need | Search pattern |
|---|---|
| Method signature & params | `sldworksapi/*InterfaceName~MethodName*` |
| All members of an interface | `sldworksapi/*InterfaceName_members*` |
| Enum/constant values | `swconst/*EnumName*` |
| Code examples | `sldworksapi/*_Example_CSharp*` or `*_Example_VB*` |
| BOM-specific constants | `swconst/*swBomType*`, `swconst/*swBOMConfiguration*` |
| Hole table constants | `swconst/*swHoleTable*` |
| Table annotation types | `swconst/*swTableAnnotationType*` |

The comprehensive C# reference is at `guides/drawing-tables-comprehensive-guide.md`.


# Drawing Tables

> Insert and edit tables on a drawing — BOM, hole, revision, bend, weldment cut list, or a free-form general table. **Default to the General table** (`IDrawingDoc.InsertTableAnnotation2`): you control rows, columns, and cell text directly, so it is more flexible and far more reliable than the specialized inserts, which depend on templates, pre-selection, and model state that often isn't there. Reach for a specialized type only when the user explicitly asks for that table and its auto-populated content (e.g. a live BOM that tracks the assembly).

## Recipe (happy path)

1. **Default to a General table.** `swDraw.InsertTableAnnotation2(x, y, anchor, cols, rows, "")` — see [How to: general table](#how-to-general-table-preferred). Set cell text with `Text2[row, col]`.
2. **Only use a specialized type when explicitly required** — a live BOM, hole table, revision table, etc. Each needs the right host (a view, or the sheet) selected first → [Specialized tables](#how-to-bom-table).
3. **Size deliberately** — `SetColumnWidth` / `SetRowHeight` in meters; lock them so SolidWorks doesn't auto-resize → [Sizing](#sizing).
4. **Anchor it** — `Anchored = true` snaps the table's corner to the sheet-format anchor so it doesn't drift when rows are added → [Anchor points](#anchor-points).
5. **Position / split if needed** — move via the table's `IAnnotation`, or `HorizontalAutoSplit` when it overruns the sheet → [Positioning](#positioning), [Splitting](#splitting-tables-that-overrun-the-sheet).
6. **Rebuild** — `ForceRebuild3(true)` + `ClearSelection2(true)` after inserts/edits.

## API quick reference

### Table types

| Table Type | Interface | Insertion Method | Template Ext |
|---|---|---|---|
| **General** (preferred) | `ITableAnnotation` | `IDrawingDoc.InsertTableAnnotation2` | `.sldtbt` |
| **BOM** | `IBomTableAnnotation` | `IView.InsertBomTable4/5/6` | `.sldbomtbt` |
| **Hole** | `IHoleTableAnnotation` | `IView.InsertHoleTable3` | `.sldholtbt` |
| **Revision** | `IRevisionTableAnnotation` | `ISheet.InsertRevisionTable2` | `.sldrevtbt` |
| **Bend** | `IBendTableAnnotation` | `IView.InsertBendTable` | `.sldbndtbt` |
| **Weldment Cut List** | `IWeldmentCutListAnnotation` | `IView.InsertWeldmentTable` | `.sldwldtbt` |
| **Punch** | `IPunchTableAnnotation` | via `IView` | — |
| **Design Table** | `IDesignTable` | Embedded Excel (**not** `ITableAnnotation`) | — |

All drawing tables **except the Design Table** inherit from `ITableAnnotation`, so everything in the next section applies to all of them.

### `ITableAnnotation` base interface

**Properties:**

| Property | Description |
|---|---|
| `RowCount` / `ColumnCount` | Visible row/column count |
| `TotalRowCount` / `TotalColumnCount` | Including hidden |
| `Anchored` | Get/set whether attached to the anchor |
| `AnchorType` | Corner anchor (`swBOMConfigurationAnchorType_e`: TopLeft=0, TopRight=1, BottomLeft=2, BottomRight=3) |
| `Title` / `TitleVisible` | Table title |
| `Text2[row, col]` | Get/set cell text (parametrized) |
| `DisplayedText2[row, col]` | Actual displayed text |
| `RowHidden[row]` / `ColumnHidden[col]` | Hide/show a row or column |
| `BorderLineWeight` / `GridLineWeight` | Line weights |

#### Sizing

```csharp
tableAnn.SetColumnWidth(col, 0.04);      // 40 mm
tableAnn.SetRowHeight(row, 0.008);       // 8 mm
double w = tableAnn.GetColumnWidth(col);
double h = tableAnn.GetRowHeight(row);
tableAnn.SetLockColumnWidth(col, true);  // prevent auto-resize
tableAnn.SetLockRowHeight(row, true);
```

#### Row / column operations

```csharp
tableAnn.InsertRow(position, true);            // true = after
tableAnn.InsertColumn2(position, true, "Title",
    (int)swInsertTableColumnPosition_e.swInsertTableColumnPosition_Last);
tableAnn.DeleteRow2(rowIndex, true);           // true = delete (not just hide)
tableAnn.DeleteColumn2(colIndex, true);
tableAnn.MoveRow(rowIndex, true);              // true = move down
tableAnn.MoveColumn(colIndex, true);           // true = move right
tableAnn.MergeCells(topRow, leftCol, bottomRow, rightCol);
tableAnn.UnmergeCells(row, col);

// IMPORTANT: delete rows bottom-to-top to avoid index shift
for (int i = tableAnn.RowCount - 1; i >= 1; i--)
    if (shouldDelete[i]) tableAnn.DeleteRow2(i, true);
```

#### Positioning

```csharp
Annotation ann = (Annotation)tableAnn.GetAnnotation();
double[] pos = (double[])ann.GetPosition();    // [x, y, z] in meters
ann.SetPosition2(newX, newY, 0);
```

#### Splitting (tables that overrun the sheet)

```csharp
tableAnn.Split(splitAtRow);                    // manual split

// Auto-split: maxRows, applyType (0=once, 1=continuously), placement (0=below, 1=right)
tableAnn.HorizontalAutoSplit(15, 1, 0);

tableAnn.StopAutoSplitting = true;             // disable
```

#### Formatting & export

```csharp
// Table-level
TextFormat tf = (TextFormat)tableAnn.GetTextFormat(0);
tf.CharHeight = 0.0028;                         // 2.8 mm
tf.TypeFaceName = "Arial";
tf.Bold = true;
tableAnn.SetTextFormat(0, false, tf);

// Cell-level
TextFormat ctf = (TextFormat)tableAnn.GetCellTextFormat(row, col);
ctf.CharHeight = 0.003;
tableAnn.SetCellTextFormat(row, col, false, ctf);

// Justification
tableAnn.CellTextHorizontalJustification[row, col] =
    (int)swTextJustification_e.swTextJustificationCenter;

// Export
tableAnn.SaveAsTemplate(@"C:\Templates\MyTemplate.sldbomtbt");
tableAnn.SaveAsText2(@"C:\Output\table.csv",
    (int)swTableTextDelimiter_e.swTableTextDelimiter_Comma);
tableAnn.SaveAsPDF(@"C:\Output\table.pdf");
```

## How to: general table (PREFERRED)

The default for any table. You own every cell, so there's no template dependency, no pre-selection ritual, and no reliance on model state — which is exactly why it's more reliable than the specialized inserts. If you need BOM-like or design-table content, build a general table and populate it from the source (e.g. `IDesignTable.GetEntryValue`) rather than inserting the specialized type.

```csharp
DrawingDoc swDraw = (DrawingDoc)swModel;

TableAnnotation tableAnn = (TableAnnotation)swDraw.InsertTableAnnotation2(
    0.1, 0.2,                                    // X, Y in meters
    (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_TopLeft,
    3,                                           // columns
    5,                                           // rows
    "");                                         // Template (empty = built-in)

tableAnn.Text2[0, 0] = "Header 1";
tableAnn.Text2[1, 0] = "Data A";

swModel.ForceRebuild3(true);
swModel.ClearSelection2(true);
```

## How to: BOM table

Only when the user wants a live bill of materials tied to the assembly. Select the host view first.

```csharp
swModel.Extension.SelectByID2(viewName, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);
View swView = (View)swModel.SelectionManager.GetSelectedObject6(1, 0);

BomTableAnnotation bomAnn = swView.InsertBomTable4(
    true,                                        // UseAnchorPoint
    0, 0,                                        // X, Y (ignored when anchor = true)
    (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_TopRight,
    (int)swBomType_e.swBomType_TopLevelOnly,
    "",                                          // Configuration (empty for TopLevelOnly)
    "",                                          // Template path (.sldbomtbt)
    false,                                       // Hidden
    0,                                           // IndentedNumberingType (swNumberingType_e)
    false);                                      // DetailedCutList

// Configure after insertion
BomFeature bomFeat = bomAnn.BomFeature;
object names, visible;
names = bomFeat.GetConfigurations(false, out visible);
// Set visible configs via bomFeat.SetConfigurations(...)
```

BOM types: `swBomType_TopLevelOnly` (1), `swBomType_PartsOnly` (2), `swBomType_Indented` (3). `InsertBomTable6` adds a `FollowAssemblyOrder` (bool) parameter at the end.

## How to: hole table

Pre-selection is mandatory — mark the datum origin then the holes before calling insert.

```csharp
// Mark 1 = datum origin vertex, Mark 2 = hole edges/faces
// Mark 4 = X-axis ref (optional), Mark 8 = Y-axis ref (optional)
ext.SelectByID2("", "VERTEX", originX, originY, 0, false, 1, null, 0);
ext.SelectByID2("", "EDGE", holeX, holeY, 0, true, 2, null, 0);

object holeTableAnn = swView.InsertHoleTable3(
    true, 0, 0,                                  // UseAnchor, X, Y
    (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_BottomLeft,
    "A",                                         // StartValue
    "",                                          // Template (.sldholtbt)
    (int)swHoleTableTagOrder_e.swHoleTableTagOrder_LeftToRight,
    (int)swHoleTableTagStyle_e.swHoleTable_Letters,
    null);                                       // ManualTags
```

## How to: revision table

Inserted on the **sheet**, not a view.

```csharp
Sheet swSheet = (Sheet)swDraw.GetCurrentSheet();

RevisionTableAnnotation revAnn = (RevisionTableAnnotation)swSheet.InsertRevisionTable2(
    true, 0, 0,
    (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_TopRight,
    "",                                          // Template (.sldrevtbt)
    (int)swRevisionTableSymbolShape_e.swRevisionTable_CircleSymbol,
    true);                                       // AutoUpdate

revAnn.AddRevision("Description of change");
revAnn.DeleteRevision(revisionIndex);
```

## How to: bend table

Select the flat-pattern view first.

```csharp
ext.SelectByID2("Flat-Pattern1", "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);

BendTableAnnotation bendAnn = (BendTableAnnotation)swView.InsertBendTable(
    true, 0, 0,
    (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_TopLeft,
    "A",                                         // StartingValue
    "");                                         // Template (.sldbndtbt)
```

## How to: weldment cut list

```csharp
ext.SelectByID2(viewName, "DRAWINGVIEW", 0, 0, 0, false, 0, null, 0);

object weldTable = swView.InsertWeldmentTable(
    true, 0, 0,
    (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_BottomLeft,
    "");                                         // Template (.sldwldtbt)
```

## How to: design table (IDesignTable — NOT ITableAnnotation)

An embedded Excel sheet of configuration parameters — a different object family from the table annotations above.

```csharp
DesignTable dt = (DesignTable)swModel.GetDesignTable();
dt.EditTable();
string val = dt.GetEntryValue(row, col);
dt.SetEntryValue(row, col, "NewValue");
dt.AddRow();
dt.UpdateTable();
dt.UpdateModel();
dt.SaveAsExcelFile(@"C:\Output\DesignTable.xlsx");
```

**Do NOT use `InsertFamilyTableNew()` to show a design table on a drawing** — it dumps an unformatted Excel blob. Instead, create a **General table** and populate it from `IDesignTable.GetEntryValue()`.

## Anchor points

Each table type has its own anchor baked into the sheet format. `UseAnchorPoint = true` (or `Anchored = true` after insertion) snaps the table's corner to it, so the table stays put when rows are added or removed.

| Table Type | Typical Anchor |
|---|---|
| BOM | BottomRight / TopRight (near title block) |
| Revision | TopRight |
| Hole | BottomLeft / TopLeft |
| Bend | TopLeft |

```csharp
tableAnn.Anchored = true;                        // attach to anchor
tableAnn.Anchored = false;                        // detach (free-floating)
tableAnn.AnchorType =
    (int)swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_TopRight;
```

## How to: iterate all tables

```csharp
string[] sheetNames = (string[])swDraw.GetSheetNames();
foreach (string sheetName in sheetNames)
{
    swDraw.ActivateSheet(sheetName);
    View view = (View)swDraw.GetFirstView();     // sheet background
    while (view != null)
    {
        TableAnnotation table = (TableAnnotation)view.GetFirstTableAnnotation();
        while (table != null)
        {
            // table.Type gives swTableAnnotationType_e:
            // 0=General, 1=BOM, 2=Hole, 4=Revision, 5=WeldmentCutList, 6=Bend, 7=Punch
            table = (TableAnnotation)table.GetNext();
        }
        view = (View)view.GetNextView();
    }
}
```

## Gotchas & fixes

- **Prefer a General table over any specialized type.** `InsertTableAnnotation2` has no template/pre-selection/model-state dependency, so it succeeds where BOM/hole/revision inserts silently return null or come back empty. Use a specialized type only when its *live, auto-populated* content is the point (a BOM that tracks the assembly, a revision table that auto-stamps). For static content, build a general table.
- **Select the right host before a specialized insert.** BOM / hole / bend / weldment insert on a **view** (`InsertBomTable4`, etc. are `IView` methods); the revision table inserts on the **sheet** (`ISheet.InsertRevisionTable2`). Wrong host → the call fails or targets nothing.
- **Pre-select for hole tables.** Mark 1 = datum-origin vertex, Mark 2 = the holes, before `InsertHoleTable3`. Skipping this returns an empty or null table.
- **Delete rows bottom-to-top.** Deleting top-down shifts every later index, so a top-down loop deletes the wrong rows. Iterate `RowCount-1 → 1`.
- **Table too big** → reduce column widths / row heights, hide columns, split the table, or reduce font.
- **Table too small** → increase `SetColumnWidth` / `SetRowHeight`, or bump `CharHeight`.
- **Tables overlap** → sum `GetColumnWidth` / `GetRowHeight` for the real extents, then offset with `SetPosition2`.
- **Position drifts when rows are added/removed** → set `Anchored = true` so the anchored corner stays fixed.
- **Too many rows for the sheet** → `HorizontalAutoSplit(maxRows, 1, 0)` for a continuous auto-split.
- **No auto-fit API** → there's no "fit to contents" call; compute the needed width manually or set generous fixed widths and lock them.
- **Rebuild after every insert/edit** → `ForceRebuild3(true)` + `ClearSelection2(true)`, or the table can stay unattached or stale until the next manual rebuild.
