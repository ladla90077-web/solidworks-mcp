# SolidWorks MCP — Professional Design Playbook

Distilled from the tutorial transcripts in `transcripts.txt`. This is the PROACTIVE design knowledge the `get_design_guidance` tool serves to Claude before it writes geometry, so the registered tools build real engineered components instead of bare blocks and cylinders. Generated from `design_library.py` — do not edit by hand.

_21 principles · 6 archetype recipes · GD&T reference._

## Universal principles

### P01 — Model design intent, not just a shape
Before sketching, decide the part's function and pick the feature that captures it: a rotational part is a REVOLVE, a machined housing is a base extrude/revolve + cuts, a thin-wall product is SURFACES->thicken, a tube run is a SWEEP along a 3D path. The shape falls out of the right feature; never default to a plain block or cylinder when the part is functional.
- _tools:_ get_design_guidance, run_and_verify

### P02 — Base-first, then features in machining order
Build the primary mass first (the revolve or the base extrude), then add bosses, then cuts/holes, then fillets and chamfers LAST — the same order a machinist would cut it. Name every feature so later steps can find it.
- _tools:_ create_extrusion, create_revolve

### P03 — Fully define every sketch (black, not blue)
Add construction geometry, relations (coincident, tangent, equal, symmetric, horizontal/vertical, concentric) and dimensions until the sketch is fully defined. Under-defined (blue) entities drift on rebuild and make patterns/mirrors unstable. Anchor splines with construction lines + tangency + pierce.
- _tools:_ run_and_verify

### P04 — Revolve about a centerline; dimension diameters across it
For any rotational part sketch a centerline through the origin on the axis, then sketch the HALF profile to one side and revolve 360 deg about it. Dimension point-to-centerline and drag past the axis to capture the full DIAMETER (not radius). An open profile auto-closes to the axis.
- _tools:_ create_revolve

### P05 — Exploit symmetry — model half, then mirror
If the part or assembly is symmetric, model one side and use Mirror Entities (sketch), Mirror feature, or Mirror Component (assembly). Halves the work and guarantees symmetry. The bottle, piston, con-rod, side-flange and manifold all mirror.
- _tools:_ create_mirror

### P06 — Pattern repeated features once; compute spacing = 360/N
Never draw N copies. Make one seed feature and pattern it: circular pattern about an axis/temporary axis with equal spacing for bolt circles, ball pockets, cooling holes; linear pattern along a direction for the engine's four journals. Angular pitch is 360/N (e.g. 16 holes -> 22.5 deg).
- _tools:_ create_circular_pattern, create_linear_pattern

### P07 — Locate hole patterns on a construction PCD circle
Draw a construction pitch-circle-diameter (PCD) circle and a centerline, place ONE seed hole coincident to it at a start angle, then circular-pattern. Carry the PCD as a toleranced dimension (the base plate uses PCD 80/90/22 at +/-0.1). This is the datum-driven way to lay out bolt circles.
- _tools:_ create_circular_pattern, create_hole_wizard

### P08 — Use robust end conditions, not hard depths, on internal features
Where a feature must terminate on another face use Up To Next, Up To Surface, Mid Plane, or Start='From Surface' instead of a typed depth. The result survives dimension edits — the housing bores and the stacked base-plate discs rely on this.
- _tools:_ run_and_verify

### P09 — Break every edge — fillets at corners, chamfers on outer edges
Real parts have no raw sharp edges. Add fillets at stress/transition corners and chamfers (e.g. 45x1, 2.1) on outer edges for handling/manufacturability. A common drawing note is 'all unspecified radii R2'. Molded/blown parts (the bottle) must have NO sharp edges at all (down to R0.25).
- _tools:_ create_fillet, create_chamfer

### P10 — Drive shapes with tangent + equal relations
Connect circles with lines made TANGENT (con-rod blank, manifold runner flange, side-flange lobes) and make matching features EQUAL so one dimension drives both. The shape then follows the key diameters automatically.
- _tools:_ run_and_verify

### P11 — Functional profiles: groove arcs, raceways, draft for casting
Cut function into the profile: a ball-bearing raceway is an ARC groove with radius slightly larger than the ball so it seats; a bottle base is a 45-deg push-up dome for strength; cast/molded walls get DRAFT. Trim the arc into the revolve profile.
- _tools:_ create_draft, create_sweep

### P12 — Reference planes/geometry before off-datum sketches
Place an offset reference plane (or axis) FIRST, then sketch on it — for crank webs, the con-rod I-beam, the manifold collector flange, loft profiles. Datum-driven placement is more robust than sketching on an existing face and parametrically editable.
- _tools:_ run_and_verify, create_loft

### P13 — Multi-body: build bodies separately, then Combine
Model distinct bodies (engine: crank/piston/rod; manifold: flanges + pipes) then Insert > Features > Combine (Add) into one solid. Lets each feature be sketched on its own clean datum before union.
- _tools:_ run_and_verify

### P14 — Surface-first then thicken for organic thin-wall parts
For bottles/cowls/ergonomic shells: revolve/extrude reference SURFACES, Offset Surface for wall thickness, Split Line to divide a face, Trim, Knit, then Thicken / knit-to-solid. Pure solid features cannot make these shapes cleanly. Reuse model edges with Convert Entities.
- _tools:_ create_surface_extrude, create_surface_revolve, create_surface_thicken

### P15 — 3D sketch + Tab for tube paths; 3D-fillet then sweep
Route tubes/manifolds with a 3D SKETCH: draw lines pressing Tab to switch the active X/Y/Z plane, fillet the 3D corners (R60/R80) into a smooth path, then Sweep a circular profile along it. A 2D path cannot capture 3D routing.
- _tools:_ create_sweep

### P16 — One multi-loop sketch -> many features via Selected Contours
Concentric circles or a multi-polygon sketch can drive several extrudes at different depths by picking Selected Contours each time (the base plate's stacked discs). Fewer sketches, shared datums, easier edits.
- _tools:_ create_extrusion

### P17 — Combine-then-Shell for a uniform-wall hollow part
To hollow a complex part with one wall thickness: Combine all bodies, then Shell removing the open faces. The manifold shells 1 mm removing its five flange faces in a single feature, guaranteeing a uniform-wall casting/weldment.
- _tools:_ create_shell

### P18 — Threads & springs: helix path + pierced circular profile
Real threads are a swept cut, not cosmetic: make a Helix (pitch + revolutions) and sweep a profile pierced to it; the pitch must exceed the profile size for clearance. A coil spring is the same helix swept with a wire circle. For standard tapped holes use the Hole Wizard with a cosmetic thread.
- _tools:_ create_thread, create_spring, create_hole_wizard

### P19 — Assembly: fix the first part, fully constrain the rest
Insert the first component (auto-fixed at origin) and DO NOT mate it. Fully constrain each later component: Concentric for rotational pairs + Coincident for axial location + Width to center. Use Copy-with-Mates to replicate identical sub-assemblies (engine cylinders), Mirror Component for symmetric halves, and a Rotary Motor in a Motion Study to validate mechanism motion.
- _tools:_ create_assembly

### P20 — Assign material early
Set the material (Plain Carbon Steel, Alloy Steel, etc.) as soon as the base body exists. It drives mass properties, the drawing BOM and RealView appearance, and is part of a complete professional part — not an afterthought.
- _tools:_ get_mass_properties

### P21 — Apply GD&T tolerancing intent to functional features
A professional part communicates what matters: form tolerances (flatness/cylindricity) on mating/sealing surfaces, Position (cylindrical zone, basic dims, ordered datums) on holes, Runout on rotating shafts. Reference datums in order; use MMC on fit-critical holes for bonus tolerance. See the GD&T reference.
- _tools:_ get_design_guidance

## Archetype recipes

### Deep-groove ball bearing
- **Archetype:** rotational precision assembly (revolved rings + patterned balls)
- **Source:** Design And Assembly of Ball Bearing
- **Summary:** Two grooved rings + a ball + a cage, each a revolve, assembled with a width mate to center the ball and circular component patterns for the rolling elements.
- **Feature sequence:**
  1. Outer ring: Front-plane sketch — horizontal centerline through origin + center rectangle; add a center-point arc (raceway groove) trimmed inside; Equal relation on the side lines; Revolve 360 about the centerline; Chamfer the corners.
  2. Inner ring: same recipe, smaller diameters, groove arc trimmed in, Equal relation, Revolve, Chamfer.
  3. Ball: half-circle + line with midpoint coincident to origin; Revolve into a sphere.
  4. Cage: extrude a ring (Mid Plane); revolved-cut a spherical ball pocket located on a construction bolt-circle; Fillet; Circular-pattern the pocket (equal spacing, 360); Shell thin; add a patterned rivet hole.
  5. Assembly: insert rings + ball + cage; Width mate centers the ball in the groove; fix one ring, float the other so it rotates; Circular Component Pattern the ball; Mirror Component for the far side; Toolbox rivets patterned to the holes; assign Plain Carbon Steel.
- **Design intent:**
  - Raceway is an ARC groove with radius slightly larger than the ball so it seats (R11 groove vs ball) — P11.
  - Centerline + diameter dimensioning on every ring profile — P04.
  - Equal relations fully define and keep each ring symmetric — P03/P10.
  - Construction bolt-circle locates the ball pockets before patterning — P07.
  - Circular pattern (equal spacing, 360) for pockets, rivets and balls; spacing 360/N — P06.
  - Width mate auto-centers the ball; Mirror Component halves the assembly — P05/P19.
- **Key dimensions:**
  - Outer ring: width 31, locating 53/65, groove R11, chamfer 2.1.
  - Inner ring: width 31, locating 25/37, groove at 8, R11, chamfer 2.1.
  - Ball ~ Ø12; cage shell 1.5; rivet hole Ø2; 8 rolling elements (360/16 = 22.5 deg layout).

### Four-cylinder engine
- **Archetype:** multi-body mechanism assembly + motion study
- **Source:** Four Cylinder engine in Solidworks
- **Summary:** Crankshaft, pistons, connecting rods, caps and pins each modeled separately, then assembled with concentric/coincident mates and animated with a rotary motor.
- **Feature sequence:**
  1. Crankshaft: base journal circle extruded; Linear-pattern the journal/web 4x (four cylinders) along a temporary axis; offset reference planes for the crank webs; drilled holes.
  2. Piston: revolve/extrude body with a pin bore and ring grooves; Mirror across the Front plane for symmetric features.
  3. Connecting rod: Front-plane sketch — big-end + small-end circles joined by two lines made TANGENT, centerline along the axis, Equal/tangent relations, fully defined; extrude mid-condition; offset plane for the I-beam web (Up-To-Surface); fillets R8/R9 + chamfer at stress corners; Convert Entities + Cut Through All for the bores; Combine bodies.
  4. Rod cap and piston pin as small separate parts.
  5. Assembly: layout sketch (symmetric relation) sets cylinder spacing; insert crank first (fixed); Concentric (big end on journal, small end on pin) + Coincident mates; Copy-with-Mates to replicate cylinders 2-4; Motion Study + Rotary Motor on the crank to animate the reciprocating pistons.
- **Design intent:**
  - Each part modeled separately then assembled bottom-up — P13.
  - Con-rod profile driven by tangent lines between the two end circles — P10.
  - Offset reference planes before the web sketches; Up-To-Surface end condition — P12/P08.
  - Linear pattern (4x) for the four journals; Mirror on the piston — P05/P06.
  - Concentric + Coincident + Width mate strategy; Copy-with-Mates propagates identical cylinders; Rotary Motor validates the kinematics — P19.
  - Fillets/chamfers at the high-cycle rod and journal transitions — P09.
- **Key dimensions:**
  - Captions are machine-translated and noisy — treat numbers as approximate.
  - Con-rod big end ~Ø33.8, small end ~Ø15-21, fillets R8/R9, chamfer 22.5 deg; rod-cap chamfer 2x45.
  - 4 cylinders, cylinder spacing ~90; rotary motor for the motion study.

### Surface-modeled plastic bottle
- **Archetype:** surface-modeled thin-wall consumer product
- **Source:** Surface Modeling - Plastic Bottle
- **Summary:** Revolve a master profile, carve grip/label recesses with through-all cuts, blend every edge, shell to a 2 mm wall, and sweep a thread on the neck.
- **Feature sequence:**
  1. Front-plane master profile: vertical centerline (height ~160), body diameters Ø50/Ø60 dimensioned across the centerline, a large R225 blend; Revolve.
  2. Body fillets R2/R4; base push-up dome (5 mm at 45 deg inward + fillet) for strength.
  3. Side-grip recesses: arc/spline profiles (R62.7, R58) Convert-Entities from the body edge, Cut Through All both directions, fillet the resulting edges (R10/R6).
  4. Label recess via spline: anchor with construction lines + tangency + pierce (fully defined); Offset Surface inward for the wall; Split Line; Surface Extrude (mid-plane) a forming surface; Trim; Knit + Thicken to a solid.
  5. Shell 2 mm wall.
  6. Neck thread: plane 2 mm down + Convert Entities; Helix (pitch 3); Right-plane half-circle profile pierced to the helix (R1.5); Sweep; tiny R0.25/R0.5 blends so nothing is sharp.
- **Design intent:**
  - Surface-first then thicken; Offset Surface defines the wall; Split Line + Trim + Knit shape the organic faces — P14.
  - Splines fully defined with construction-line anchors + tangency + pierce so they don't drift — P03.
  - NO sharp edges anywhere (blow molding) — every transition filleted/chamfered down to R0.25 — P09.
  - Base push-up dome for strength; Convert Entities reuses model edges — P11.
  - Helix + swept thread; pitch must exceed the profile size for clearance — P18.
- **Key dimensions:**
  - Height 160, neck 10; body Ø50/Ø60; main blend R225; body fillets R2/R4.
  - Side cuts arc R62.7 / R58; edge fillets R10/R6; shell wall 2 mm.
  - Thread: helix pitch 3, profile R1.5, blends R0.25/R0.5, plane offset 2 from top.

### Exhaust manifold
- **Archetype:** swept tubular weldment/casting (4-into-1)
- **Source:** Solidworks tutorial Exhaust manifold
- **Summary:** Flat bolt-hole flanges built first, connected by pipes swept along 3D-sketch paths, mirrored, combined into one body, then shelled 1 mm hollow.
- **Feature sequence:**
  1. Runner flange: fully-defined Front-plane profile (line at 38 deg, equal/tangent/midpoint relations, R15/R50), Extrude 8 mm; bolt holes Ø16 Cut Through All; Linear-pattern the flange 4x (spacing 120).
  2. Collector flange: offset reference plane 171 from Top; circular flange with a 6-bolt circle + central bore (Ø168 PCD, Ø16 holes), Extrude 8 mm.
  3. Pipe paths: seed a Ø70 circle on the runner face; open a 3D SKETCH, draw the route pressing Tab to switch planes (segments ~112/50), fillet the 3D corners R60/R80; Sweep the circle along the path. Repeat for the second runner.
  4. Construct a mid plane (3D-sketch line + Plane) and Mirror the two swept pipe bodies to make all four runners.
  5. Combine (Add) pipes + flanges into one body; Shell 1 mm removing the five flange faces; blend junctions R10; chamfer 45x1; assign material.
- **Design intent:**
  - Solid flanges first, then pipes swept along 3D paths — P15.
  - 3D sketch with Tab plane-switching + 3D fillets (R60/R80) for the routing — P15.
  - Fully-defined flange sketch (equal/tangent/midpoint/coincident) so the pattern/mirror are stable — P03/P10.
  - Linear pattern 4x + Mirror of the pipe bodies exploits symmetry — P05/P06.
  - Combine then a single Shell hollows the whole manifold to a uniform 1 mm wall — P13/P17.
- **Key dimensions:**
  - Runner flange angle 38, line 130, outer Ø30, span 100, R15/R50, thickness 8.
  - Bolt holes Ø16 @ 68; flange pattern spacing 120, 4 instances; collector plane 171 from Top.
  - Collector PCD Ø168, holes Ø16, thickness 8; pipe profile Ø70; 3D path 112/50, fillets R60/R80; shell 1 mm; chamfer 45x1.

### Revolved machined housing (Exercise-263)
- **Archetype:** axisymmetric machined housing with bosses + bolt ports
- **Source:** SolidWorks Tutorial for beginners Exercise-263
- **Summary:** A single revolve forms the body, then prismatic bosses, a loft, internal mid-plane cores, Hole-Wizard tapped holes and a bolt-circle pattern turn it into a real housing.
- **Feature sequence:**
  1. Revolve base: Front-plane half-profile (lines + arc, tangent at the line/arc point) about a construction centerline; flange Ø100x12, bores Ø40/Ø52, overall length 133.
  2. Bosses: square 64x64 with R8 corner on the Right plane (located 86 from origin); a Ø64 boss with tangent relations using Direction-2 Up-To-Next; a side flange on a plane offset 73 from Front (mirror-entities lobed profile, power-trim, extrude 12); a Loft boss between Ø52 and Ø46.
  3. Internal coring: Front-plane rectangle giving 6 mm wall, Mid-Plane cut (width 52); a second cored cut on an offset plane; Up-To-Next cuts to inner walls.
  4. Threads: Hole Wizard tapped M33/M39/M48 (Up To Next) with cosmetic threads; a revolve-cut internal recess.
  5. Bolt circle: Ø12 hole on a construction PCD Ø75 at a 45 deg start angle, Circular-pattern 4x; default R2 fillets on remaining edges.
- **Design intent:**
  - Base-first axisymmetric revolve captures the rotational intent in one feature — P02/P04.
  - Fully-defined sketches; tangent at line/arc transitions called 'important' — P03/P10.
  - Symmetry via mirror entities; Mid-Plane cuts keep the 6 mm walls symmetric — P05.
  - Up-To-Next / Direction-2 end conditions instead of typed depths — P08.
  - Hole Wizard + cosmetic threads for standard taps; circular pattern for the bolt circle — P07/P18.
  - Uniform R2 fillets as the default-break note; functional R8/R4 at boss transitions — P09.
- **Key dimensions:**
  - Overall length 133; flange Ø100x12; bores Ø40/Ø52; loft Ø52->Ø46.
  - Square boss 64x64 R8 (offset 86); side flange on plane offset 73, extrude 12; wall 6 mm, core width 52.
  - Taps M33x2 / M39x2 / M48x2; bolt circle Ø12 on PCD 75, 4 holes at 90 deg; default fillet R2.

### Mounting base plate
- **Archetype:** stacked-disc machined mounting plate
- **Source:** SolidWorks Tutorial-Mounting Base Plate Modeling
- **Summary:** Concentric discs stacked by thickness layers, triangular webs, three toleranced bolt circles and a central tapped boss — built from one shared sketch via Selected Contours.
- **Feature sequence:**
  1. Base ring: Top-plane concentric circles Ø110/Ø100; extrude the annulus contour 10 mm; extrude the inner contour 10 mm with Start='From Surface' (net 20 mm). Assign Alloy Steel.
  2. Webs: inscribed triangle tangent to the inner circle, circular sketch-pattern about center; extrude selected triangle contours 10 mm, then 3 of them 5 mm; fillet R5/R6.
  3. Central boss: Ø15 circle extruded 5 mm; Hole Wizard tapped M10x1.5 (thread depth 20, hole through all, cosmetic thread).
  4. Bolt circles: construction PCDs Ø80/Ø90/Ø22 (each +/-0.1); seed Ø10 / Ø4 holes coincident to the PCD; circular-pattern (3x and 6x) about center; center bore Ø10; Cut Through All.
  5. Center cutouts: arc slots (R2 ends on PCD 46, 100 deg span) patterned 3x; construction-driven triangles; a hexagon pocket — each cut to its own depth from the same sketch via Selected Contours.
- **Design intent:**
  - Base-first, layer-by-layer thickness stack (0->10->20->30->35) — P02.
  - Start='From Surface' grows the second disc off the first face (rebuild-robust) — P08.
  - Selected Contours: one sketch drives many extrudes at different depths — P16.
  - Circular sketch-patterns + tangent/coincident relations build the symmetric webs and bolt circles, all fully defined — P03/P06.
  - Bolt circles carry symmetric +/-0.1 tolerances (functional location) — P07/P21.
  - Hole Wizard M10x1.5; default web fillets R5/R6 for manufacturability — P09/P18.
- **Key dimensions:**
  - Discs Ø110/Ø100, layers 10+10 (20 from base); webs 10 then 5; boss Ø15 (top at 35).
  - Bolt circles PCD Ø80 (3xØ10), Ø90 (6xØ4), Ø22 (6xØ4), all +/-0.1; center bore Ø10.
  - Tapped M10x1.5 thread depth 20; web fillets R5/R6; arc slots PCD 46, R2 ends, 100 deg, 3x.

## GD&T reference

GD&T tolerances FEATURES (a surface, hole or slot) rather than dimensions, so a drawing communicates what actually matters for function. 14 characteristics in 5 categories, applied through a Feature Control Frame: symbol | tolerance (a zone WIDTH; prefix a diameter symbol for a cylindrical zone) | ordered datums | modifiers.

**Categories**
- **Form (no datum):** Flatness, Straightness, Circularity, Cylindricity — apply to mating/sealing faces and to shaft surfaces.
- **Orientation (vs a datum):** Parallelism, Perpendicularity, Angularity — e.g. a hole axis perpendicular to its face.
- **Location:** Position (the common one: cylindrical zone about a TRUE position set by BASIC dims, ordered datums, MMC bonus) — for holes/patterns. (Concentricity/Symmetry removed in ASME 2018.)
- **Profile:** Profile of a Surface / of a Line — controls form+orientation+location of a contour at once.
- **Runout:** Circular & Total Runout about a datum axis — for rotating shafts to limit eccentricity/vibration.

**Datums** — Letter + datum triangle. A datum feature is restrained against a datum simulator to remove the 6 DOF: primary removes 3, secondary 2, tertiary 1 -> a Datum Reference Frame. ORDER matters for repeatability and is listed in the frame.

**Modifiers** — MMC (M): feature at max material (smallest hole / largest pin); an oversize hole earns BONUS tolerance = actual - MMC. LMC (L): least material. RFS (default): no bonus. ASME Rule #1 (Envelope): size limits also control form — at MMC the form must be perfect, guaranteeing fit.

**Rules of thumb**
- Form tolerance on any surface that must seal or seat (flatness on a flange face, cylindricity on a bearing journal).
- Position (not +/-) on holes and bolt patterns: cylindrical zone, basic dims, datums in order; the hole's primary datum is usually the face it is perpendicular to.
- Runout on rotating shaft features.
- MMC on clearance/fit holes to claim bonus tolerance.
