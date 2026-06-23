# SolidWorks MCP - Learned Lessons

Auto-generated from `rules.json`. Each rule was recorded the first time an error was hit and fixed, so the same mistake is avoided next time. **Do not edit by hand** - use the `learn_rule` tool.

_36 rules._

## assembly

### r0023 - Plane-mate alignment must be consistent across a component's 3 mates
- **Symptom:** A subsequent component constrained by 3 orthogonal plane mates reports MateDistanceDim / MateCoincident error_code 51 (over-defined / conflicting) on the plane(s) where alignment was flipped.
- **Cause:** Mixing swMateAlignALIGNED (0) and swMateAlignANTI_ALIGNED (1) inconsistently across a component's three orthogonal plane mates creates a conflicting rotation constraint. Using ANTI on one plane merely to push a component to the opposite side (instead of a signed distance) fights the other two ALIGNED mates.
- **Fix:** Decide whether the component needs to ROTATE. If it needs NO rotation (same orientation as assembly), use ALIGNED (0) on all three plane mates and place opposite-side components with a NEGATIVE distance offset (flip = offset<0), never anti-align. If it needs a 180-deg rotation about an axis, flip alignment to ANTI (1) on exactly the two planes whose normals reverse under that rotation and keep ALIGNED on the third (e.g. 180 about Z: Right ANTI + Top ANTI + Front ALIGNED). Keep all three mates internally consistent.
- **Good:** `' Screw mirrored to -X (no rotation): all ALIGNED, negative offset`
- _hits: 0 · since 2026-06-21_

### r0031 - Select a component's hole/planar face by LOCAL geometry — Component2.GetBody returns part-local coords
- **Symptom:** Need to select a specific hole's cylindrical face (or top/bottom planar face) of an inserted component for a mate or a motor axis, but face names are unstable and several holes share the same radius.
- **Cause:** Picking faces by assembly-space coordinate is fragile because the mate solver moves parts after each mate.
- **Fix:** comp.GetBody returns the body with geometry in the PART's LOCAL coordinate system (independent of where the solver placed the component). Iterate GetFirstFace/GetNextFace: for a hole use Surface.CylinderParams (index 0..2 = axis origin xyz, 3..5 = axis dir, 6 = radius) and match on radius AND local centre cp(0),cp(1); for a face use Face2.Normal Z-sign (+Z = top, -Z = bottom). Select for AddMate5 with a SelectData whose Mark=1 (Face2.Select4 with append=True on the 2nd entity).
- **Good:** `If Abs(cp(6)-HR)<2E-5 And Abs(cp(0)-localCx)<3E-4 And Abs(cp(1))<3E-4 Then Set faceOut = fc`
- _hits: 0 · since 2026-06-23_

### r0032 - Match inserted components by InStr on Name2 (instance-suffixed); AssemblyDoc has no GetMateCount
- **Symptom:** Looking up a component by the plain name you set via Component2.Name2 fails (returns Nothing); or swAsm.GetMateCount() / swAsm.GetMates aborts an inline .swb with no log (ran=False).
- **Cause:** Component2.Name2 reports the instance form e.g. "Crank_216-1" (the rename to "Crank" does not round-trip to a plain-equality match), and IAssemblyDoc exposes no GetMateCount method, so calling it raises a runtime error that silently kills the macro.
- **Fix:** Match with InStr(1, comp.Name2, "Crank", vbTextCompare) > 0 over swAsm.GetComponents(True). Do not call GetMateCount; judge mate creation by AddMate5 returning non-Nothing plus a post-rebuild GetErrorCode2 scan.
- **Good:** `If InStr(1, c.Name2, "Rocker", vbTextCompare) > 0 Then Set rockerC = c`
- _hits: 0 · since 2026-06-23_

### r0033 - AddMate5 ByRef ErrorStatus = 1 means SUCCESS (swAddMateError_NoError)
- **Symptom:** AddMate5 returns ByRef err=1 for every mate and you conclude the mates failed.
- **Cause:** swAddMateError_e: 1 = NoError (success). The error values are 0 = unknown error, 2 = bad mate type, 3 = bad alignment, 4 = IncorrectSelections, 5 = OverDefinedAssembly, 6 = bad gear ratios.
- **Fix:** Treat err=1 together with a non-Nothing return as SUCCESS. Only 0/4/5 indicate real failure. (Clarifies r0013.)
- _hits: 0 · since 2026-06-23_

## design

### r0017 - GD&T basics: tolerance features, not just dimensions
- **Symptom:** Need professional tolerancing intent for parts that must fit/function.
- **Cause:** Dimensional tolerances do not capture functional intent (flatness of a sealing face, perpendicularity of a hole axis).
- **Fix:** GD&T applies tolerances to FEATURES via feature control frames across 5 categories: Form (flatness, straightness, circularity, cylindricity), Orientation, Location, Profile, Runout. Reference datums (letter + triangle) for orientation/location. Use form tolerances on mating/sealing surfaces and position on holes.
- _hits: 0 · since 2026-06-20_

### r0024 - Tubular runs: route a 3D sketch, fillet the corners, then sweep
- **Symptom:** A pipe/manifold/cable run cannot be made from a single 2D sketch and a sweep fails or looks crude.
- **Cause:** 3D routing (out of the flange, then down to the collector) cannot be captured by one planar sketch.
- **Fix:** Open a 3D Sketch, draw the route pressing Tab to switch the active X/Y/Z plane, fillet the 3D corners (e.g. R60/R80) into a smooth path, then Sweep a circular profile along it. Build rigid flanges first as solids. See get_design_guidance("exhaust manifold").
- **Good:** `' 3D sketch path + R60/R80 corner fillets, sweep Ø70 profile`
- _hits: 0 · since 2026-06-21_

### r0025 - Hollow multi-body parts: Combine (Add) then a single Shell
- **Symptom:** Shelling a part made of several bodies (pipes + flanges) gives non-uniform walls or fails.
- **Cause:** Shell needs one body; separate bodies shell independently.
- **Fix:** Insert > Features > Combine (Add) all bodies into one solid, THEN Shell removing the open faces - one feature gives a uniform wall (the manifold shells 1 mm removing its 5 flange faces). See get_design_guidance("manifold").
- **Good:** `' Combine Add all bodies; Shell 0.001 remove flange faces`
- _hits: 0 · since 2026-06-21_

### r0026 - Layered/stacked parts: extrude base-first, grow with From Surface / Selected Contours
- **Symptom:** A part with several thickness layers ends up as one dull block, or depths break when a dimension changes.
- **Cause:** Typed absolute depths and a single closed profile cannot express a layered, datum-driven stack.
- **Fix:** Draw concentric loops in ONE sketch and extrude different Selected Contours to different depths; use Start=From Surface so a layer grows off the previous face (rebuild-robust). See get_design_guidance("mounting base plate").
- **Good:** `' Extrude inner contour, Start = From Surface (net stack height)`
- _hits: 0 · since 2026-06-21_

### r0027 - Bolt circles: seed one hole on a construction PCD, then circular-pattern
- **Symptom:** Multiple bolt holes drawn one-by-one are misplaced or hard to edit.
- **Cause:** Hand-placing N holes is error-prone and not parametric.
- **Fix:** Draw a construction PCD circle + a centerline, place ONE seed hole coincident at a start angle, then circular-pattern it (equal spacing, 360; pitch = 360/N). Carry the PCD as a toleranced dimension. See get_design_guidance("bolt circle").
- **Good:** `' seed hole on construction PCD Ø80; circular pattern 3x equal`
- _hits: 0 · since 2026-06-21_

### r0028 - Exploit symmetry: model half then mirror (entities/feature/component)
- **Symptom:** Symmetric features modeled twice drift out of symmetry or double the work.
- **Cause:** Duplicating symmetric geometry by hand is wasteful and error-prone.
- **Fix:** Model one side and use Mirror Entities (sketch), Mirror feature (solid), or Mirror Component (assembly). Guarantees symmetry and halves the work. See get_design_guidance for the bottle/piston/manifold examples.
- **Good:** `' InsertMirrorFeature about the Right plane`
- _hits: 0 · since 2026-06-21_

### r0029 - Finish like a real part: base-first order, then break every edge
- **Symptom:** The model is a raw prism/cylinder with sharp edges - not a professional component.
- **Cause:** Defaulting to the simplest shape that rebuilds clean, with no design intent or edge treatment.
- **Fix:** Build base mass first, then bosses, then cuts/holes, then fillets+chamfers LAST. Break every edge (fillets at stress corners, chamfers on outer edges; unspecified radii often R2). Call get_design_guidance(<part>) first to pick the right archetype.
- **Good:** `' fillets at corners + 45x1 chamfer on outer edges, applied last`
- _hits: 0 · since 2026-06-21_

### r0030 - Flat link/bar with two pin holes: one nested sketch (rectangle + 2 circles) → single boss extrude
- **Symptom:** Need a flat linkage bar (crank/coupler/rocker/ground) with two through-holes at a given pin-to-pin spacing L, color-coded, saved as its own part.
- **Cause:** Separate boss-then-cut works but is two features; a single nested-contour boss is simpler and verified to produce the holes.
- **Fix:** On the Front plane, ONE sketch: CreateCornerRectangle spanning (-W/2,-W/2)..(L+W/2,+W/2) [capture as Variant, NOT Set - see r0002], plus two CreateCircle at (0,0) and (L,0). Exit sketch, re-select it (SelectLatestSketch), FeatureExtrusion3 thickness T. The nested inner circles become holes -> verify with Surface.IsCylinder count == 2. Colour via swModel.MaterialPropertyValues (9-double array; 0..2 = R,G,B in 0..1). Save via swModelExt.SaveAs(path, 0, swSaveAsOptions_Silent, Nothing, errs, warns). Holes end up at local (0,0) and (L,0) - reuse those centres later for assembly mates.
- **Good:** `vRect = swSketchMgr.CreateCornerRectangle(-W/2#,-W/2#,0#, L+W/2#,W/2#,0#) ' Variant`
- _hits: 0 · since 2026-06-23_

## motion

### r0034 - Motion Analysis study with result plots — verified end-to-end API workflow
- **Symptom:** Need a SOLIDWORKS Motion (Motion Analysis) study on an assembly with a driving motor and angular/linear result plots, created entirely from VBA.
- **Cause:** The motion-study API spans add-in loading, study type, motor definition, calculate, results and plot-feature-data objects across two type libraries.
- **Fix:** 1) Load the solver add-in: swApp.LoadAddIn(\"C:\\Program Files\\SOLIDWORKS Corp\\SOLIDWORKS\\cmotionsw.dll\") (returns 2 when loaded). 2) Set mgr = swModelDocExt.GetMotionStudyManager(); Set study = mgr.GetMotionStudy(\"Motion Study 1\"); study.Activate. 3) study.StudyType = 4 (swMotionStudyTypeCosmosMotion = Motion Analysis; requires Premium). 4) Motor: Set motor = study.CreateDefinition(swFmAEMRotationalMotor); motor.DirectionReference = <cyl/planar/conical face, circular edge, axis or plane>; motor.ConstantSpeedMotor <rpm>; Set f = study.CreateFeature(motor). 5) study.SetDuration secs; study.Calculate. 6) Set res = study.GetResults(4); build pfd=res.CreatePlotFeatureData(), xfd=res.CreatePlotXAxisFeatureData(), yfd=res.CreatePlotYAxisFeatureData(); yfd.Type=swMotionPlotAxisType (ANGULAR_DISP=9, ANGULAR_VELOCITY=10, ANGULAR_ACCEL=11, TRANS_DISP=6, TRANS_VELOCITY=7, time X-axis=0); yfd.Component (X=1,Y=2,Z=3); yfd.Entities=Array(face); res.InsertPlotFeature pfd,xfd,yfd. For raw numbers: po=res.GetValues(pfd,xfd,(yArray)); po.GetXAxis(); po.GetYAxis(yfd). BINDING: late-bind MotionStudyManager / MotionStudy / CosmosMotionStudyResults / MotionPlotFeatureOutput As Object (SwMotionStudy lib is NOT auto-referenced in an inline .swb); SimulationMotorFeatureData / MotionPlotFeatureData / MotionPlotAxisFeatureData are in the sldworks lib so early-binding is fine.
- _hits: 0 · since 2026-06-23_

### r0035 - Motor produces zero motion unless you call ConstantSpeedMotor (RPM) — not MotionType/Velocity
- **Symptom:** Motor feature is created and study.Calculate returns True, but the mechanism does not move — the driven part's angular displacement is constant across the whole run (swing = 0).
- **Cause:** Setting SimulationMotorFeatureData.MotionType + .Velocity properties alone does NOT define the drive magnitude, so the motor runs at zero speed and the assembly stays in its assembled pose.
- **Fix:** Call the drive METHOD on the motor feature data: motor.ConstantSpeedMotor(rpm) for constant speed (Speed argument is in RPM), or OscillatingMotor / DistanceMotor / InterpolatedMotor for those types. Set motor.DirectionReference to the rotation-axis entity before study.CreateFeature. Verify by extracting GetYAxis(angular-disp) min/max and confirming a non-zero swing.
- **Good:** `motor.DirectionReference = crankAxisFace : motor.ConstantSpeedMotor 30#   ' 30 RPM = 1 rev / 2 s`
- _hits: 0 · since 2026-06-23_

### r0036 - Never delete the default Motion Study 1 — CreateMotionStudy returns Nothing when zero studies exist
- **Symptom:** After DeleteMotionStudy on every study, mgr.CreateMotionStudy() returns Nothing; GetMotionStudyCount=0 and GetMotionStudyNames is empty, leaving the assembly with no usable motion study.
- **Cause:** The default \"Motion Study 1\" is created by the MotionManager UI, and the API cannot bootstrap a study from a count of zero — CreateMotionStudy only adds reliably when at least one study already exists.
- **Fix:** Keep the default study and reuse mgr.GetMotionStudy(\"Motion Study 1\"). To reset, replace/edit its motor and plot features rather than deleting the study. If a study was already deleted to zero, recover it by opening the assembly once in the SOLIDWORKS UI (which recreates Motion Study 1).
- _hits: 0 · since 2026-06-23_

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
- _hits: 2 · since 2026-06-20_

### r0012 - Do not mate the auto-fixed first assembly component
- **Symptom:** Assembly has an over-defined mate (red X, code 51) right after insertion.
- **Cause:** The first component added to an assembly is FIXED at the origin; mating its planes to the assembly planes adds redundant constraints and over-defines it.
- **Fix:** Leave the first component fixed (no mates). Fully constrain each SUBSEQUENT component relative to the first (or to the assembly) - e.g. stack c2 on c1 with Front+Right coincident and Top distance = part thickness.
- _hits: 2 · since 2026-06-20_

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
