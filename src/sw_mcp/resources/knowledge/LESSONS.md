# SolidWorks MCP - Learned Lessons

Auto-generated from `rules.json`. Each rule was recorded the first time an error was hit and fixed, so the same mistake is avoided next time. **Do not edit by hand** - use the `learn_rule` tool.

_22 rules._

## design

### r0017 - GD&T basics: tolerance features, not just dimensions
- **Symptom:** Need professional tolerancing intent for parts that must fit/function.
- **Cause:** Dimensional tolerances do not capture functional intent (flatness of a sealing face, perpendicularity of a hole axis).
- **Fix:** GD&T applies tolerances to FEATURES via feature control frames across 5 categories: Form (flatness, straightness, circularity, cylindricity), Orientation, Location, Profile, Runout. Reference datums (letter + triangle) for orientation/location. Use form tolerances on mating/sealing surfaces and position on holes.
- _hits: 0 · since 2026-06-20_

## vba

### r0001 - API booleans return +1 in .swb - never use bitwise 'If Not'
- **Symptom:** A selection/boolean helper clearly returns True, yet the 'If Not x' guard takes the failure branch.
- **Cause:** In an on-the-fly .swb macro, SolidWorks API VARIANT_BOOL returns arrive as +1 (not VBA's True == -1). VBA 'Not' is bitwise, so 'Not 1' = -2 (truthy) and the guard misfires.
- **Fix:** Test API booleans with 'If x = False Then' (never 'If Not x'). Object checks ('Is Nothing') are unaffected.
- **Good:** `If okSel = False Then ... End If`
- _hits: 1 · since 2026-06-20_

### r0002 - Create*Rectangle returns a Variant array - do not use Set
- **Symptom:** Run-time error 424 'Object required' on Set seg = swSketchMgr.Create...Rectangle(...).
- **Cause:** CreateCenterRectangle/CreateCornerRectangle return a Variant ARRAY of sketch segments, not a single object; Set on a non-object raises 424.
- **Fix:** Capture as Variant and check IsArray: Dim v As Variant: v = swSketchMgr.CreateCenterRectangle(...): If IsArray(v) = False Then ... . (CreateCircleByRadius returns a single SketchSegment, so Set is fine there.)
- **Good:** `Dim v As Variant`
- _hits: 1 · since 2026-06-20_

### r0003 - MsgBox blocks automation - use the silent log instead
- **Symptom:** A macro call hangs / times out.
- **Cause:** A modal MsgBox (or SendMsgToUser) blocks RunMacro2 until dismissed, deadlocking the COM thread.
- **Fix:** In automated macros replace MsgBox with SWMCP_Log step/status/message lines; the server reads the log for per-step status. A dialog watchdog also auto-dismisses strays.
- **Good:** `SWMCP_Log "base", "ERROR", "Base extrusion failed"`
- _hits: 0 · since 2026-06-20_

### r0004 - Never hardcode template paths; abort if none configured
- **Symptom:** NewDocument returns Nothing / part is not created.
- **Cause:** No default template is configured, or a hardcoded template path does not exist on this machine.
- **Fix:** Get the template via GetUserPreferenceStringValue(swDefaultTemplatePart=8) and abort cleanly (SWMCP_Log ERROR) if it is empty.
- **Good:** `tpl = swApp.GetUserPreferenceStringValue(8)`
- _hits: 0 · since 2026-06-20_

### r0005 - Select reference planes by tree position, not by name
- **Symptom:** SelectByID2("Top Plane","PLANE",...) returns False even though the name matches on screen.
- **Cause:** Name-based plane selection is unreliable across templates / languages.
- **Fix:** Use the SelectStdPlane helper (walks the tree, selects the Nth RefPlane feature directly): 1=Front, 2=Top, 3=Right.
- **Good:** `okSel = SelectStdPlane(2, False, 0)  ' Top`
- _hits: 0 · since 2026-06-20_

### r0006 - InsertRib silently no-ops from API; use a thin-boss gusset
- **Symptom:** swFeatMgr.InsertRib runs without error but no Rib feature appears in the tree.
- **Cause:** InsertRib is unreliable on programmatically-built sketches and on solids without bounding walls.
- **Fix:** Build the gusset as a closed triangle bridging the two inner faces, extruded thin (mid-plane) - geometrically equivalent and reliable. A rib also needs walls to bridge; it cannot form above a flat block.
- **Good:** `3x CreateLine closed triangle on Right plane + FeatureExtrusion3 thin both-dir`
- _hits: 0 · since 2026-06-20_

### r0007 - Right (YZ) plane sketch coordinate mapping
- **Symptom:** CreateLine/CreateCircle on the Right plane lands in the wrong place or returns Nothing.
- **Cause:** Sketch primitives use the sketch-plane LOCAL 2D coords (3rd arg must be 0), not model XYZ.
- **Fix:** On the Right plane, local (u,v) maps to model (Z=-u, Y=v). On Top plane local=(X,Z); on Front plane local=(X,Y); 3rd CreateLine arg is always 0.
- _hits: 0 · since 2026-06-20_

### r0008 - No log at all + ran=False means a VBA compile error
- **Symptom:** run_and_verify returns ran=False with an empty log (not even the init step).
- **Cause:** Under Option Explicit, a referenced Sub/Function/variable that is not defined is a COMPILE error, so main() never executes and nothing is logged.
- **Fix:** Ensure every helper the macro calls (RenameFeature, FindLastSketchName, FindLastRefPlaneName, FindFeatureByName, etc.) is defined in the macro. Check for typos in identifiers and enum names.
- _hits: 0 · since 2026-06-20_

### r0009 - Use bare enum member names, not qualified container names
- **Symptom:** Macro fails to compile (ran=False, no log) on a line referencing an enum like swWzdHoleTypes_e.swWzdCounterBore.
- **Cause:** The guessed enum container type name (swWzdHoleTypes_e etc.) may be wrong; a wrong identifier is a compile error under Option Explicit.
- **Fix:** Use the bare enum member name (swWzdCounterBore, swStandardAnsiMetric, swEndCondThroughAll) - SolidWorks enum members are globally accessible in VBA. Verify the exact name via docs_lookup_enum if unsure.
- _hits: 0 · since 2026-06-20_

### r0010 - AddComponent5 needs the loaded doc exact path (use partDoc.GetPathName)
- **Symptom:** AddComponent5 and AddComponent4 both return Nothing even though the part is loaded (GetType=1) and the assembly is active (GetType=2).
- **Cause:** The path passed to AddComponent5 must match the in-memory document path exactly; a path that differs in slashes/case from the loaded doc fails silently.
- **Fix:** After OpenDoc6, capture loadedPath = partDoc.GetPathName and pass THAT to AddComponent5/AddComponent4. Also use native backslash paths for SaveAs/OpenDoc6. Preload the part (OpenDoc6 Silent) and ActivateDoc3 the assembly (by StripExt(GetTitle)) before inserting.
- _hits: 0 · since 2026-06-20_

### r0011 - GetErrorCode2 requires the ByRef IsWarning arg (else detection silently fails)
- **Symptom:** run_and_verify reports success on a model that visibly has errored features (e.g. over-defined mates with a red X).
- **Cause:** IFeature.GetErrorCode2(ByRef IsWarning) needs the IsWarning argument; calling it with no args always throws, so a try/except wrapper silently returns 0 and every feature looks clean.
- **Fix:** Call GetErrorCode2 with a VT_BYREF VT_BOOL VARIANT and also DESCEND into sub-features (GetFirstSubFeature/GetNextSubFeature) - mates live as sub-features of the MateGroup. A non-zero code with IsWarning False is a real error (51 = over-defined).
- _hits: 0 · since 2026-06-20_

### r0012 - Do not mate the auto-fixed first assembly component
- **Symptom:** Assembly has an over-defined mate (red X, code 51) right after insertion.
- **Cause:** The first component added to an assembly is FIXED at the origin; mating its planes to the assembly planes adds redundant constraints and over-defines it.
- **Fix:** Leave the first component fixed (no mates). Fully constrain each SUBSEQUENT component relative to the first (or to the assembly) - e.g. stack c2 on c1 with Front+Right coincident and Top distance = part thickness.
- _hits: 0 · since 2026-06-20_

### r0013 - Mate component planes by instance name string; ignore AddMate5 ByRef error
- **Symptom:** AddMate5 returns err=1 (IncorrectSelections) OR returns err=1 even though the mate is created correctly.
- **Cause:** Selecting a component plane via comp.FirstFeature is ambiguous with duplicate part instances; and AddMate5 ByRef ErrorStatus is unreliable in an inline .swb (returns 1 even on valid mates).
- **Fix:** Select the component-instance plane by name: "<Plane>@<ComponentName>@<AssemblyTitle>" with mark 1. Judge mate success by (swMate Is Not Nothing) + the post-rebuild GetErrorCode2 scan, NOT by the AddMate5 ByRef error code.
- _hits: 0 · since 2026-06-20_

### r0014 - Surface modeling workflow: build surfaces -> trim -> knit -> thicken to solid
- **Symptom:** Need a complex organic/thin-wall shape (bottle, manifold) that pure solid features cannot make cleanly.
- **Cause:** Professional surface workflow builds reference surfaces then converts to a solid.
- **Fix:** Typical pro pipeline (from the Plastic Bottle tutorial): revolve/extrude a base surface; OffsetSurface for wall offset; SplitLine to divide a face; surface Extrude (mid-plane); Trim surface (keep/remove selections); Knit the surfaces; Thicken or Knit-with-create-solid to get a solid; then fillet/shell. Reuse model edges with Convert Entities.
- _hits: 0 · since 2026-06-20_

### r0015 - Dimension diameters with a centerline (revolve profiles)
- **Symptom:** Revolve profiles need diameter dimensions, not radius.
- **Cause:** Pros sketch a centerline on the axis; dimensioning across it and dragging past gives the full DIAMETER automatically.
- **Fix:** Draw a centerline through the origin on the axis of revolution; when dimensioning a point to the centerline, drag the dimension to the far side to get the diameter value (2x radius). Always include the centerline in the revolve sketch.
- _hits: 0 · since 2026-06-20_

### r0016 - Fully define sketches (esp. splines) before building features
- **Symptom:** Geometry drifts or rebuilds unpredictably; spline-based surfaces are unstable.
- **Cause:** Under-defined sketches (blue entities) move; pros fully define every sketch (black).
- **Fix:** Add construction lines + dimensions + relations (tangency, coincident-on-edge, horizontal/vertical, equal) until the sketch is fully defined. For splines: constrain endpoints to edges, set tangency/elevation, and dimension control points via construction lines.
- _hits: 0 · since 2026-06-20_

### r0018 - Surface methods are Subs/Boolean on IModelDoc2 - call as statements
- **Symptom:** Set swFeat = swModel.FeatureExtruRefSurface2(...) or InsertPlanarRefSurface() fails (err 424/450), or surface call compile-errors.
- **Cause:** Many surface methods live on IModelDoc2 (swModel), NOT FeatureManager, and are Subs (void) or return Boolean - so they cannot be assigned with Set.
- **Fix:** Call them as statements (no Set): swModel.FeatureExtruRefSurface2 <args>; for InsertPlanarRefSurface use If swModel.InsertPlanarRefSurface()=False. Then get the new feature via FindLastFeature(). Surface creation on swModel: InsertPlanarRefSurface, InsertRevolvedRefSurface, InsertSweepRefSurface2, InsertLoftRefSurface2, InsertSewRefSurface, FeatureExtruRefSurface2, FeatureBossThicken (surface->solid).
- _hits: 0 · since 2026-06-20_

### r0019 - Verify arg COUNT from the VB declaration, not the Parameters list
- **Symptom:** An early-bound API call compile-errors (ran=False, no log) even though arg names look right.
- **Cause:** The docs Parameters section can list more items than the real method takes (e.g. FeatureExtruRefSurface2 lists 20 but takes 17; FeatureBossThicken lists 4 but takes 3). Wrong arg count on an early-bound call is a COMPILE error.
- **Fix:** Count args from the actual VB Sub/Function declaration line (render the doc page and count the parameter anchors), not the prose Parameters list. Use swSheetBody (not swSurfaceBody) for surface bodies in GetBodies2.
- _hits: 0 · since 2026-06-20_

### r0020 - Sheet metal base flange: mirror the official example args
- **Symptom:** InsertSheetMetalBaseFlange2 returns Nothing / creates no feature.
- **Cause:** Wrong arg values (esp. DirToUse=0, UseDefaultRelief=True with zero relief).
- **Fix:** Use the proven example args: InsertSheetMetalBaseFlange2(Thk, False, Rad, ExtrudeDist1, ExtrudeDist2, False, 0, 0, DirToUse=1, PCBA, UseDefaultRelief=False, ReliefType=2, 0.0001, 0.0001, 0.5, True, Merge=False, UseFeatScope=True, True). PCBA = an uninitialised Dim ... As Object (= Nothing). CLOSED profile -> flat plate (ExtrudeDist ignored); OPEN profile (e.g. an L of 2 lines) -> bent part, ExtrudeDist1 = depth, bend added at each vertex.
- _hits: 0 · since 2026-06-20_

### r0021 - Edge flange needs a profile sketch; prefer open-profile base flange for simple bends
- **Symptom:** InsertSheetMetalEdgeFlange2 returns Nothing even with a valid edge selected.
- **Cause:** Edge flange expects a flange profile sketch (the official example builds one with InsertSketchForEdgeFlange); passing Nothing/empty sketch arrays returns Nothing.
- **Fix:** For a simple bent part, use an OPEN-profile base flange (one feature, no edge selection). For a true edge flange, first create the profile sketch on the edge face via InsertSketchForEdgeFlange, then pass it in the SketchFeats array.
- _hits: 0 · since 2026-06-20_

### r0022 - Close documents between operations - accumulated open docs degrade SolidWorks
- **Symptom:** Generators that pass in isolation fail intermittently when many run in sequence (plane/edge selection or feature creation fails).
- **Cause:** Each new part/assembly stays open; dozens of open documents make SolidWorks sluggish and selection/state unreliable.
- **Fix:** Close documents between independent operations (app.CloseAllDocuments True). In the test suite an autouse fixture closes all docs after each test.
- _hits: 0 · since 2026-06-20_
