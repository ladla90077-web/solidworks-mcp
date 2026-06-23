"""Professional design knowledge — the *proactive* counterpart to knowledge.py.

knowledge.py is REACTIVE: it surfaces fixes after a macro errors. This module is
PROACTIVE: before Claude builds anything, `get_design_guidance` returns how a
professional would actually model that class of part — the feature sequence,
the design-intent practices, the key dimensions and the relevant GD&T — so the
generated VBA produces a real engineered component instead of the simplest shape
that happens to rebuild clean (a bare block or cylinder).

The content is distilled from the SolidWorks tutorial transcripts in
`transcripts.txt` (ball bearing, four-cylinder engine, surface-modeled plastic
bottle, exhaust manifold, GD&T, Exercise-263 revolved housing, mounting base
plate). Each RECIPE is an archetype; the PRINCIPLES are the universal practices
those tutorials share. `render_playbook_md()` regenerates the human-readable
DESIGN_PLAYBOOK.md.
"""
from __future__ import annotations

from .util import RESOURCES_DIR

PLAYBOOK_FILE = RESOURCES_DIR / "knowledge" / "DESIGN_PLAYBOOK.md"


# ===========================================================================
# Universal professional-design principles (shared by every transcript).
# Each: id, title, detail, keywords (for matching), tools (registered MCP tools
# / VBA features that realise it).
# ===========================================================================
PRINCIPLES: list[dict] = [
    {
        "id": "P01",
        "title": "Model design intent, not just a shape",
        "detail": "Before sketching, decide the part's function and pick the "
                  "feature that captures it: a rotational part is a REVOLVE, a "
                  "machined housing is a base extrude/revolve + cuts, a thin-wall "
                  "product is SURFACES->thicken, a tube run is a SWEEP along a 3D "
                  "path. The shape falls out of the right feature; never default "
                  "to a plain block or cylinder when the part is functional.",
        "keywords": ["intent", "professional", "function", "start", "plan", "approach"],
        "tools": ["get_design_guidance", "run_and_verify"],
    },
    {
        "id": "P02",
        "title": "Base-first, then features in machining order",
        "detail": "Build the primary mass first (the revolve or the base "
                  "extrude), then add bosses, then cuts/holes, then fillets and "
                  "chamfers LAST — the same order a machinist would cut it. Name "
                  "every feature so later steps can find it.",
        "keywords": ["base", "order", "sequence", "first", "machining"],
        "tools": ["create_extrusion", "create_revolve"],
    },
    {
        "id": "P03",
        "title": "Fully define every sketch (black, not blue)",
        "detail": "Add construction geometry, relations (coincident, tangent, "
                  "equal, symmetric, horizontal/vertical, concentric) and "
                  "dimensions until the sketch is fully defined. Under-defined "
                  "(blue) entities drift on rebuild and make patterns/mirrors "
                  "unstable. Anchor splines with construction lines + tangency + "
                  "pierce.",
        "keywords": ["sketch", "fully define", "relation", "constraint", "spline", "stable"],
        "tools": ["run_and_verify"],
    },
    {
        "id": "P04",
        "title": "Revolve about a centerline; dimension diameters across it",
        "detail": "For any rotational part sketch a centerline through the origin "
                  "on the axis, then sketch the HALF profile to one side and "
                  "revolve 360 deg about it. Dimension point-to-centerline and "
                  "drag past the axis to capture the full DIAMETER (not radius). "
                  "An open profile auto-closes to the axis.",
        "keywords": ["revolve", "centerline", "diameter", "rotational", "shaft", "ring", "axis"],
        "tools": ["create_revolve"],
    },
    {
        "id": "P05",
        "title": "Exploit symmetry — model half, then mirror",
        "detail": "If the part or assembly is symmetric, model one side and use "
                  "Mirror Entities (sketch), Mirror feature, or Mirror Component "
                  "(assembly). Halves the work and guarantees symmetry. The "
                  "bottle, piston, con-rod, side-flange and manifold all mirror.",
        "keywords": ["mirror", "symmetry", "symmetric", "half"],
        "tools": ["create_mirror"],
    },
    {
        "id": "P06",
        "title": "Pattern repeated features once; compute spacing = 360/N",
        "detail": "Never draw N copies. Make one seed feature and pattern it: "
                  "circular pattern about an axis/temporary axis with equal "
                  "spacing for bolt circles, ball pockets, cooling holes; linear "
                  "pattern along a direction for the engine's four journals. "
                  "Angular pitch is 360/N (e.g. 16 holes -> 22.5 deg).",
        "keywords": ["pattern", "circular", "linear", "repeat", "instances", "bolt"],
        "tools": ["create_circular_pattern", "create_linear_pattern"],
    },
    {
        "id": "P07",
        "title": "Locate hole patterns on a construction PCD circle",
        "detail": "Draw a construction pitch-circle-diameter (PCD) circle and a "
                  "centerline, place ONE seed hole coincident to it at a start "
                  "angle, then circular-pattern. Carry the PCD as a toleranced "
                  "dimension (the base plate uses PCD 80/90/22 at +/-0.1). This is "
                  "the datum-driven way to lay out bolt circles.",
        "keywords": ["pcd", "bolt circle", "pitch circle", "hole pattern", "flange"],
        "tools": ["create_circular_pattern", "create_hole_wizard"],
    },
    {
        "id": "P08",
        "title": "Use robust end conditions, not hard depths, on internal features",
        "detail": "Where a feature must terminate on another face use Up To Next, "
                  "Up To Surface, Mid Plane, or Start='From Surface' instead of a "
                  "typed depth. The result survives dimension edits — the housing "
                  "bores and the stacked base-plate discs rely on this.",
        "keywords": ["end condition", "up to next", "up to surface", "mid plane", "from surface", "rebuild"],
        "tools": ["run_and_verify"],
    },
    {
        "id": "P09",
        "title": "Break every edge — fillets at corners, chamfers on outer edges",
        "detail": "Real parts have no raw sharp edges. Add fillets at stress/"
                  "transition corners and chamfers (e.g. 45x1, 2.1) on outer "
                  "edges for handling/manufacturability. A common drawing note is "
                  "'all unspecified radii R2'. Molded/blown parts (the bottle) "
                  "must have NO sharp edges at all (down to R0.25).",
        "keywords": ["fillet", "chamfer", "edge", "round", "break", "stress", "corner"],
        "tools": ["create_fillet", "create_chamfer"],
    },
    {
        "id": "P10",
        "title": "Drive shapes with tangent + equal relations",
        "detail": "Connect circles with lines made TANGENT (con-rod blank, "
                  "manifold runner flange, side-flange lobes) and make matching "
                  "features EQUAL so one dimension drives both. The shape then "
                  "follows the key diameters automatically.",
        "keywords": ["tangent", "equal", "relation", "con-rod", "connecting rod", "lobe"],
        "tools": ["run_and_verify"],
    },
    {
        "id": "P11",
        "title": "Functional profiles: groove arcs, raceways, draft for casting",
        "detail": "Cut function into the profile: a ball-bearing raceway is an ARC "
                  "groove with radius slightly larger than the ball so it seats; a "
                  "bottle base is a 45-deg push-up dome for strength; cast/molded "
                  "walls get DRAFT. Trim the arc into the revolve profile.",
        "keywords": ["groove", "raceway", "arc", "draft", "cast", "bearing", "seat"],
        "tools": ["create_draft", "create_sweep"],
    },
    {
        "id": "P12",
        "title": "Reference planes/geometry before off-datum sketches",
        "detail": "Place an offset reference plane (or axis) FIRST, then sketch on "
                  "it — for crank webs, the con-rod I-beam, the manifold collector "
                  "flange, loft profiles. Datum-driven placement is more robust "
                  "than sketching on an existing face and parametrically editable.",
        "keywords": ["reference plane", "offset plane", "datum", "geometry", "axis"],
        "tools": ["run_and_verify", "create_loft"],
    },
    {
        "id": "P13",
        "title": "Multi-body: build bodies separately, then Combine",
        "detail": "Model distinct bodies (engine: crank/piston/rod; manifold: "
                  "flanges + pipes) then Insert > Features > Combine (Add) into "
                  "one solid. Lets each feature be sketched on its own clean datum "
                  "before union.",
        "keywords": ["multibody", "multi-body", "combine", "body", "boolean", "union"],
        "tools": ["run_and_verify"],
    },
    {
        "id": "P14",
        "title": "Surface-first then thicken for organic thin-wall parts",
        "detail": "For bottles/cowls/ergonomic shells: revolve/extrude reference "
                  "SURFACES, Offset Surface for wall thickness, Split Line to "
                  "divide a face, Trim, Knit, then Thicken / knit-to-solid. Pure "
                  "solid features cannot make these shapes cleanly. Reuse model "
                  "edges with Convert Entities.",
        "keywords": ["surface", "thicken", "bottle", "thin wall", "offset surface", "trim", "knit", "split line", "organic"],
        "tools": ["create_surface_extrude", "create_surface_revolve", "create_surface_thicken"],
    },
    {
        "id": "P15",
        "title": "3D sketch + Tab for tube paths; 3D-fillet then sweep",
        "detail": "Route tubes/manifolds with a 3D SKETCH: draw lines pressing Tab "
                  "to switch the active X/Y/Z plane, fillet the 3D corners "
                  "(R60/R80) into a smooth path, then Sweep a circular profile "
                  "along it. A 2D path cannot capture 3D routing.",
        "keywords": ["3d sketch", "tab", "tube", "pipe", "manifold", "sweep", "path", "route"],
        "tools": ["create_sweep"],
    },
    {
        "id": "P16",
        "title": "One multi-loop sketch -> many features via Selected Contours",
        "detail": "Concentric circles or a multi-polygon sketch can drive several "
                  "extrudes at different depths by picking Selected Contours each "
                  "time (the base plate's stacked discs). Fewer sketches, shared "
                  "datums, easier edits.",
        "keywords": ["selected contours", "contour", "multi-loop", "concentric", "stacked", "layer"],
        "tools": ["create_extrusion"],
    },
    {
        "id": "P17",
        "title": "Combine-then-Shell for a uniform-wall hollow part",
        "detail": "To hollow a complex part with one wall thickness: Combine all "
                  "bodies, then Shell removing the open faces. The manifold shells "
                  "1 mm removing its five flange faces in a single feature, "
                  "guaranteeing a uniform-wall casting/weldment.",
        "keywords": ["shell", "hollow", "uniform wall", "combine", "wall thickness", "manifold"],
        "tools": ["create_shell"],
    },
    {
        "id": "P18",
        "title": "Threads & springs: helix path + pierced circular profile",
        "detail": "Real threads are a swept cut, not cosmetic: make a Helix "
                  "(pitch + revolutions) and sweep a profile pierced to it; the "
                  "pitch must exceed the profile size for clearance. A coil spring "
                  "is the same helix swept with a wire circle. For standard "
                  "tapped holes use the Hole Wizard with a cosmetic thread.",
        "keywords": ["thread", "helix", "spring", "tapped", "screw", "coil", "pitch"],
        "tools": ["create_thread", "create_spring", "create_hole_wizard"],
    },
    {
        "id": "P19",
        "title": "Assembly: fix the first part, fully constrain the rest",
        "detail": "Insert the first component (auto-fixed at origin) and DO NOT "
                  "mate it. Fully constrain each later component: Concentric for "
                  "rotational pairs + Coincident for axial location + Width to "
                  "center. Use Copy-with-Mates to replicate identical sub-"
                  "assemblies (engine cylinders), Mirror Component for symmetric "
                  "halves, and a Rotary Motor in a Motion Study to validate "
                  "mechanism motion.",
        "keywords": ["assembly", "mate", "concentric", "coincident", "width", "motion", "fix", "copy with mates"],
        "tools": ["create_assembly"],
    },
    {
        "id": "P20",
        "title": "Assign material early",
        "detail": "Set the material (Plain Carbon Steel, Alloy Steel, etc.) as "
                  "soon as the base body exists. It drives mass properties, the "
                  "drawing BOM and RealView appearance, and is part of a complete "
                  "professional part — not an afterthought.",
        "keywords": ["material", "mass", "steel", "appearance", "density"],
        "tools": ["get_mass_properties"],
    },
    {
        "id": "P21",
        "title": "Apply GD&T tolerancing intent to functional features",
        "detail": "A professional part communicates what matters: form tolerances "
                  "(flatness/cylindricity) on mating/sealing surfaces, Position "
                  "(cylindrical zone, basic dims, ordered datums) on holes, Runout "
                  "on rotating shafts. Reference datums in order; use MMC on "
                  "fit-critical holes for bonus tolerance. See the GD&T reference.",
        "keywords": ["gd&t", "gdt", "tolerance", "datum", "position", "flatness", "runout", "mmc", "fit"],
        "tools": ["get_design_guidance"],
    },
]


# ===========================================================================
# Archetype recipes (distilled from the transcripts).
# ===========================================================================
RECIPES: list[dict] = [
    {
        "name": "Deep-groove ball bearing",
        "archetype": "rotational precision assembly (revolved rings + patterned balls)",
        "source": "Design And Assembly of Ball Bearing",
        "keywords": ["bearing", "ball bearing", "race", "raceway", "ring", "rotational",
                     "groove", "cage", "rolling element"],
        "summary": "Two grooved rings + a ball + a cage, each a revolve, assembled "
                   "with a width mate to center the ball and circular component "
                   "patterns for the rolling elements.",
        "feature_sequence": [
            "Outer ring: Front-plane sketch — horizontal centerline through origin + center rectangle; add a center-point arc (raceway groove) trimmed inside; Equal relation on the side lines; Revolve 360 about the centerline; Chamfer the corners.",
            "Inner ring: same recipe, smaller diameters, groove arc trimmed in, Equal relation, Revolve, Chamfer.",
            "Ball: half-circle + line with midpoint coincident to origin; Revolve into a sphere.",
            "Cage: extrude a ring (Mid Plane); revolved-cut a spherical ball pocket located on a construction bolt-circle; Fillet; Circular-pattern the pocket (equal spacing, 360); Shell thin; add a patterned rivet hole.",
            "Assembly: insert rings + ball + cage; Width mate centers the ball in the groove; fix one ring, float the other so it rotates; Circular Component Pattern the ball; Mirror Component for the far side; Toolbox rivets patterned to the holes; assign Plain Carbon Steel.",
        ],
        "design_intent": [
            "Raceway is an ARC groove with radius slightly larger than the ball so it seats (R11 groove vs ball) — P11.",
            "Centerline + diameter dimensioning on every ring profile — P04.",
            "Equal relations fully define and keep each ring symmetric — P03/P10.",
            "Construction bolt-circle locates the ball pockets before patterning — P07.",
            "Circular pattern (equal spacing, 360) for pockets, rivets and balls; spacing 360/N — P06.",
            "Width mate auto-centers the ball; Mirror Component halves the assembly — P05/P19.",
        ],
        "key_dimensions": [
            "Outer ring: width 31, locating 53/65, groove R11, chamfer 2.1.",
            "Inner ring: width 31, locating 25/37, groove at 8, R11, chamfer 2.1.",
            "Ball ~ Ø12; cage shell 1.5; rivet hole Ø2; 8 rolling elements (360/16 = 22.5 deg layout).",
        ],
    },
    {
        "name": "Four-cylinder engine",
        "archetype": "multi-body mechanism assembly + motion study",
        "source": "Four Cylinder engine in Solidworks",
        "keywords": ["engine", "crankshaft", "piston", "connecting rod", "conrod", "con-rod",
                     "mechanism", "motion", "cylinder", "pin", "kinematic"],
        "summary": "Crankshaft, pistons, connecting rods, caps and pins each modeled "
                   "separately, then assembled with concentric/coincident mates and "
                   "animated with a rotary motor.",
        "feature_sequence": [
            "Crankshaft: base journal circle extruded; Linear-pattern the journal/web 4x (four cylinders) along a temporary axis; offset reference planes for the crank webs; drilled holes.",
            "Piston: revolve/extrude body with a pin bore and ring grooves; Mirror across the Front plane for symmetric features.",
            "Connecting rod: Front-plane sketch — big-end + small-end circles joined by two lines made TANGENT, centerline along the axis, Equal/tangent relations, fully defined; extrude mid-condition; offset plane for the I-beam web (Up-To-Surface); fillets R8/R9 + chamfer at stress corners; Convert Entities + Cut Through All for the bores; Combine bodies.",
            "Rod cap and piston pin as small separate parts.",
            "Assembly: layout sketch (symmetric relation) sets cylinder spacing; insert crank first (fixed); Concentric (big end on journal, small end on pin) + Coincident mates; Copy-with-Mates to replicate cylinders 2-4; Motion Study + Rotary Motor on the crank to animate the reciprocating pistons.",
        ],
        "design_intent": [
            "Each part modeled separately then assembled bottom-up — P13.",
            "Con-rod profile driven by tangent lines between the two end circles — P10.",
            "Offset reference planes before the web sketches; Up-To-Surface end condition — P12/P08.",
            "Linear pattern (4x) for the four journals; Mirror on the piston — P05/P06.",
            "Concentric + Coincident + Width mate strategy; Copy-with-Mates propagates identical cylinders; Rotary Motor validates the kinematics — P19.",
            "Fillets/chamfers at the high-cycle rod and journal transitions — P09.",
        ],
        "key_dimensions": [
            "Captions are machine-translated and noisy — treat numbers as approximate.",
            "Con-rod big end ~Ø33.8, small end ~Ø15-21, fillets R8/R9, chamfer 22.5 deg; rod-cap chamfer 2x45.",
            "4 cylinders, cylinder spacing ~90; rotary motor for the motion study.",
        ],
    },
    {
        "name": "Surface-modeled plastic bottle",
        "archetype": "surface-modeled thin-wall consumer product",
        "source": "Surface Modeling - Plastic Bottle",
        "keywords": ["bottle", "surface", "thin wall", "plastic", "blow mold", "shell",
                     "spline", "thicken", "organic", "consumer"],
        "summary": "Revolve a master profile, carve grip/label recesses with "
                   "through-all cuts, blend every edge, shell to a 2 mm wall, and "
                   "sweep a thread on the neck.",
        "feature_sequence": [
            "Front-plane master profile: vertical centerline (height ~160), body diameters Ø50/Ø60 dimensioned across the centerline, a large R225 blend; Revolve.",
            "Body fillets R2/R4; base push-up dome (5 mm at 45 deg inward + fillet) for strength.",
            "Side-grip recesses: arc/spline profiles (R62.7, R58) Convert-Entities from the body edge, Cut Through All both directions, fillet the resulting edges (R10/R6).",
            "Label recess via spline: anchor with construction lines + tangency + pierce (fully defined); Offset Surface inward for the wall; Split Line; Surface Extrude (mid-plane) a forming surface; Trim; Knit + Thicken to a solid.",
            "Shell 2 mm wall.",
            "Neck thread: plane 2 mm down + Convert Entities; Helix (pitch 3); Right-plane half-circle profile pierced to the helix (R1.5); Sweep; tiny R0.25/R0.5 blends so nothing is sharp.",
        ],
        "design_intent": [
            "Surface-first then thicken; Offset Surface defines the wall; Split Line + Trim + Knit shape the organic faces — P14.",
            "Splines fully defined with construction-line anchors + tangency + pierce so they don't drift — P03.",
            "NO sharp edges anywhere (blow molding) — every transition filleted/chamfered down to R0.25 — P09.",
            "Base push-up dome for strength; Convert Entities reuses model edges — P11.",
            "Helix + swept thread; pitch must exceed the profile size for clearance — P18.",
        ],
        "key_dimensions": [
            "Height 160, neck 10; body Ø50/Ø60; main blend R225; body fillets R2/R4.",
            "Side cuts arc R62.7 / R58; edge fillets R10/R6; shell wall 2 mm.",
            "Thread: helix pitch 3, profile R1.5, blends R0.25/R0.5, plane offset 2 from top.",
        ],
    },
    {
        "name": "Exhaust manifold",
        "archetype": "swept tubular weldment/casting (4-into-1)",
        "source": "Solidworks tutorial Exhaust manifold",
        "keywords": ["manifold", "exhaust", "tube", "pipe", "runner", "collector",
                     "flange", "header", "swept", "3d sketch"],
        "summary": "Flat bolt-hole flanges built first, connected by pipes swept "
                   "along 3D-sketch paths, mirrored, combined into one body, then "
                   "shelled 1 mm hollow.",
        "feature_sequence": [
            "Runner flange: fully-defined Front-plane profile (line at 38 deg, equal/tangent/midpoint relations, R15/R50), Extrude 8 mm; bolt holes Ø16 Cut Through All; Linear-pattern the flange 4x (spacing 120).",
            "Collector flange: offset reference plane 171 from Top; circular flange with a 6-bolt circle + central bore (Ø168 PCD, Ø16 holes), Extrude 8 mm.",
            "Pipe paths: seed a Ø70 circle on the runner face; open a 3D SKETCH, draw the route pressing Tab to switch planes (segments ~112/50), fillet the 3D corners R60/R80; Sweep the circle along the path. Repeat for the second runner.",
            "Construct a mid plane (3D-sketch line + Plane) and Mirror the two swept pipe bodies to make all four runners.",
            "Combine (Add) pipes + flanges into one body; Shell 1 mm removing the five flange faces; blend junctions R10; chamfer 45x1; assign material.",
        ],
        "design_intent": [
            "Solid flanges first, then pipes swept along 3D paths — P15.",
            "3D sketch with Tab plane-switching + 3D fillets (R60/R80) for the routing — P15.",
            "Fully-defined flange sketch (equal/tangent/midpoint/coincident) so the pattern/mirror are stable — P03/P10.",
            "Linear pattern 4x + Mirror of the pipe bodies exploits symmetry — P05/P06.",
            "Combine then a single Shell hollows the whole manifold to a uniform 1 mm wall — P13/P17.",
        ],
        "key_dimensions": [
            "Runner flange angle 38, line 130, outer Ø30, span 100, R15/R50, thickness 8.",
            "Bolt holes Ø16 @ 68; flange pattern spacing 120, 4 instances; collector plane 171 from Top.",
            "Collector PCD Ø168, holes Ø16, thickness 8; pipe profile Ø70; 3D path 112/50, fillets R60/R80; shell 1 mm; chamfer 45x1.",
        ],
    },
    {
        "name": "Revolved machined housing (Exercise-263)",
        "archetype": "axisymmetric machined housing with bosses + bolt ports",
        "source": "SolidWorks Tutorial for beginners Exercise-263",
        "keywords": ["housing", "machined", "revolve", "boss", "port", "bore",
                     "tapped", "exercise", "flange housing", "casting"],
        "summary": "A single revolve forms the body, then prismatic bosses, a loft, "
                   "internal mid-plane cores, Hole-Wizard tapped holes and a "
                   "bolt-circle pattern turn it into a real housing.",
        "feature_sequence": [
            "Revolve base: Front-plane half-profile (lines + arc, tangent at the line/arc point) about a construction centerline; flange Ø100x12, bores Ø40/Ø52, overall length 133.",
            "Bosses: square 64x64 with R8 corner on the Right plane (located 86 from origin); a Ø64 boss with tangent relations using Direction-2 Up-To-Next; a side flange on a plane offset 73 from Front (mirror-entities lobed profile, power-trim, extrude 12); a Loft boss between Ø52 and Ø46.",
            "Internal coring: Front-plane rectangle giving 6 mm wall, Mid-Plane cut (width 52); a second cored cut on an offset plane; Up-To-Next cuts to inner walls.",
            "Threads: Hole Wizard tapped M33/M39/M48 (Up To Next) with cosmetic threads; a revolve-cut internal recess.",
            "Bolt circle: Ø12 hole on a construction PCD Ø75 at a 45 deg start angle, Circular-pattern 4x; default R2 fillets on remaining edges.",
        ],
        "design_intent": [
            "Base-first axisymmetric revolve captures the rotational intent in one feature — P02/P04.",
            "Fully-defined sketches; tangent at line/arc transitions called 'important' — P03/P10.",
            "Symmetry via mirror entities; Mid-Plane cuts keep the 6 mm walls symmetric — P05.",
            "Up-To-Next / Direction-2 end conditions instead of typed depths — P08.",
            "Hole Wizard + cosmetic threads for standard taps; circular pattern for the bolt circle — P07/P18.",
            "Uniform R2 fillets as the default-break note; functional R8/R4 at boss transitions — P09.",
        ],
        "key_dimensions": [
            "Overall length 133; flange Ø100x12; bores Ø40/Ø52; loft Ø52->Ø46.",
            "Square boss 64x64 R8 (offset 86); side flange on plane offset 73, extrude 12; wall 6 mm, core width 52.",
            "Taps M33x2 / M39x2 / M48x2; bolt circle Ø12 on PCD 75, 4 holes at 90 deg; default fillet R2.",
        ],
    },
    {
        "name": "Mounting base plate",
        "archetype": "stacked-disc machined mounting plate",
        "source": "SolidWorks Tutorial-Mounting Base Plate Modeling",
        "keywords": ["base plate", "mounting", "plate", "stacked", "disc", "web",
                     "bolt circle", "boss", "flange plate"],
        "summary": "Concentric discs stacked by thickness layers, triangular webs, "
                   "three toleranced bolt circles and a central tapped boss — built "
                   "from one shared sketch via Selected Contours.",
        "feature_sequence": [
            "Base ring: Top-plane concentric circles Ø110/Ø100; extrude the annulus contour 10 mm; extrude the inner contour 10 mm with Start='From Surface' (net 20 mm). Assign Alloy Steel.",
            "Webs: inscribed triangle tangent to the inner circle, circular sketch-pattern about center; extrude selected triangle contours 10 mm, then 3 of them 5 mm; fillet R5/R6.",
            "Central boss: Ø15 circle extruded 5 mm; Hole Wizard tapped M10x1.5 (thread depth 20, hole through all, cosmetic thread).",
            "Bolt circles: construction PCDs Ø80/Ø90/Ø22 (each +/-0.1); seed Ø10 / Ø4 holes coincident to the PCD; circular-pattern (3x and 6x) about center; center bore Ø10; Cut Through All.",
            "Center cutouts: arc slots (R2 ends on PCD 46, 100 deg span) patterned 3x; construction-driven triangles; a hexagon pocket — each cut to its own depth from the same sketch via Selected Contours.",
        ],
        "design_intent": [
            "Base-first, layer-by-layer thickness stack (0->10->20->30->35) — P02.",
            "Start='From Surface' grows the second disc off the first face (rebuild-robust) — P08.",
            "Selected Contours: one sketch drives many extrudes at different depths — P16.",
            "Circular sketch-patterns + tangent/coincident relations build the symmetric webs and bolt circles, all fully defined — P03/P06.",
            "Bolt circles carry symmetric +/-0.1 tolerances (functional location) — P07/P21.",
            "Hole Wizard M10x1.5; default web fillets R5/R6 for manufacturability — P09/P18.",
        ],
        "key_dimensions": [
            "Discs Ø110/Ø100, layers 10+10 (20 from base); webs 10 then 5; boss Ø15 (top at 35).",
            "Bolt circles PCD Ø80 (3xØ10), Ø90 (6xØ4), Ø22 (6xØ4), all +/-0.1; center bore Ø10.",
            "Tapped M10x1.5 thread depth 20; web fillets R5/R6; arc slots PCD 46, R2 ends, 100 deg, 3x.",
        ],
    },
]


# ===========================================================================
# GD&T quick reference (from the "Understanding GD&T" transcript).
# ===========================================================================
GDNT: dict = {
    "summary": "GD&T tolerances FEATURES (a surface, hole or slot) rather than "
               "dimensions, so a drawing communicates what actually matters for "
               "function. 14 characteristics in 5 categories, applied through a "
               "Feature Control Frame: symbol | tolerance (a zone WIDTH; prefix a "
               "diameter symbol for a cylindrical zone) | ordered datums | "
               "modifiers.",
    "categories": {
        "Form (no datum)": "Flatness, Straightness, Circularity, Cylindricity — "
                           "apply to mating/sealing faces and to shaft surfaces.",
        "Orientation (vs a datum)": "Parallelism, Perpendicularity, Angularity — "
                                    "e.g. a hole axis perpendicular to its face.",
        "Location": "Position (the common one: cylindrical zone about a TRUE "
                    "position set by BASIC dims, ordered datums, MMC bonus) — for "
                    "holes/patterns. (Concentricity/Symmetry removed in ASME 2018.)",
        "Profile": "Profile of a Surface / of a Line — controls form+orientation+"
                   "location of a contour at once.",
        "Runout": "Circular & Total Runout about a datum axis — for rotating "
                  "shafts to limit eccentricity/vibration.",
    },
    "datums": "Letter + datum triangle. A datum feature is restrained against a "
              "datum simulator to remove the 6 DOF: primary removes 3, secondary "
              "2, tertiary 1 -> a Datum Reference Frame. ORDER matters for "
              "repeatability and is listed in the frame.",
    "modifiers": "MMC (M): feature at max material (smallest hole / largest pin); "
                 "an oversize hole earns BONUS tolerance = actual - MMC. LMC (L): "
                 "least material. RFS (default): no bonus. ASME Rule #1 (Envelope): "
                 "size limits also control form — at MMC the form must be perfect, "
                 "guaranteeing fit.",
    "rules_of_thumb": [
        "Form tolerance on any surface that must seal or seat (flatness on a "
        "flange face, cylindricity on a bearing journal).",
        "Position (not +/-) on holes and bolt patterns: cylindrical zone, basic "
        "dims, datums in order; the hole's primary datum is usually the face it "
        "is perpendicular to.",
        "Runout on rotating shaft features.",
        "MMC on clearance/fit holes to claim bonus tolerance.",
    ],
}


# ===========================================================================
# Lookup / matching API.
# ===========================================================================
def list_recipes() -> list[dict]:
    """Index of available archetype recipes (name, archetype, keywords, summary)."""
    return [
        {"name": r["name"], "archetype": r["archetype"],
         "keywords": r["keywords"], "summary": r["summary"], "source": r["source"]}
        for r in RECIPES
    ]


def _recipe_score(query_text: str, query_words: set[str],
                  keywords: list[str], recipe_text: str) -> int:
    """Relevance of a recipe to the QUERY: a recipe keyword phrase mentioned in
    the query scores high; a query word found in the recipe text scores lower."""
    score = 0
    for kw in keywords:
        if kw in query_text:
            score += 3
        elif any(qw in kw.split() for qw in query_words):
            score += 2
    for qw in query_words:
        if qw in recipe_text:
            score += 1
    return score


def _principle_hit(query_text: str, query_words: set[str], keywords: list[str]) -> bool:
    """Strict relevance test for PRINCIPLES (favours precision so the result is
    a focused set, not the whole catalogue): a keyword phrase appears in the
    query, or a query word equals a keyword token."""
    kw_tokens = {tok for kw in keywords for tok in kw.split()}
    if any(kw in query_text for kw in keywords):
        return True
    return bool(query_words & kw_tokens)


def get_guidance(query: str = "") -> dict:
    """Return professional design guidance for a part description or topic.

    Matches `query` (e.g. 'ball bearing', 'mounting bracket with bolt holes',
    'hollow manifold', 'shaft tolerance') against the recipes and principles and
    returns the relevant feature sequence, design-intent practices, key
    dimensions, principles and — when the query is about tolerancing — the GD&T
    reference. With an empty query it returns the full principle set + recipe
    index so Claude can orient before designing.
    """
    q = (query or "").lower()
    words = {w for w in re_split(q) if len(w) > 2}

    if not q:
        return {
            "intro": "Consult this BEFORE designing so the registered tools "
                     "(run_and_verify, create_*) are used with professional "
                     "design intent. Pass a part description to get the matching "
                     "archetype recipe.",
            "principles": PRINCIPLES,
            "recipes": list_recipes(),
            "gdnt_available": True,
        }

    scored = sorted(
        ((_recipe_score(q, words, r["keywords"],
                        (r["name"] + " " + r["archetype"] + " " + r["summary"] + " " +
                         " ".join(r["keywords"])).lower()), r)
          for r in RECIPES),
        key=lambda t: t[0], reverse=True,
    )
    matched_recipes = [r for s, r in scored if s > 0][:2]

    matched_principles = [
        p for p in PRINCIPLES if _principle_hit(q, words, p["keywords"])
    ]
    # Always include the foundational principles so even an off-target query
    # still nudges toward professional modeling.
    foundational = [p for p in PRINCIPLES if p["id"] in ("P01", "P02", "P03", "P09")]
    for p in foundational:
        if p not in matched_principles:
            matched_principles.append(p)

    want_gdnt = bool(words & {"tolerance", "tolerances", "gd&t", "gdt", "datum",
                              "datums", "position", "flatness", "runout", "mmc",
                              "fit", "fits", "inspection", "tolerancing"})

    result: dict = {
        "query": query,
        "recipes": matched_recipes if matched_recipes
        else [{"note": "No exact archetype; apply the principles below and the "
               "closest recipe.", "recipe_index": list_recipes()}],
        "principles": matched_principles,
    }
    if want_gdnt or any("tolerance" in di.lower() or "gd&t" in di.lower()
                        for r in matched_recipes for di in r.get("design_intent", [])):
        result["gdnt"] = GDNT
    return result


def re_split(text: str) -> list[str]:
    """Tiny word splitter (avoids importing re for one call site)."""
    out, cur = [], []
    for ch in text:
        if ch.isalnum() or ch in "&":
            cur.append(ch)
        else:
            if cur:
                out.append("".join(cur))
                cur = []
    if cur:
        out.append("".join(cur))
    return out


# ===========================================================================
# Human-readable playbook generation.
# ===========================================================================
def render_playbook_md() -> str:
    lines = [
        "# SolidWorks MCP — Professional Design Playbook",
        "",
        "Distilled from the tutorial transcripts in `transcripts.txt`. This is the "
        "PROACTIVE design knowledge the `get_design_guidance` tool serves to Claude "
        "before it writes geometry, so the registered tools build real engineered "
        "components instead of bare blocks and cylinders. Generated from "
        "`design_library.py` — do not edit by hand.",
        "",
        f"_{len(PRINCIPLES)} principles · {len(RECIPES)} archetype recipes · GD&T reference._",
        "",
        "## Universal principles",
        "",
    ]
    for p in PRINCIPLES:
        lines.append(f"### {p['id']} — {p['title']}")
        lines.append(p["detail"])
        if p.get("tools"):
            lines.append(f"- _tools:_ {', '.join(p['tools'])}")
        lines.append("")

    lines.append("## Archetype recipes")
    lines.append("")
    for r in RECIPES:
        lines.append(f"### {r['name']}")
        lines.append(f"- **Archetype:** {r['archetype']}")
        lines.append(f"- **Source:** {r['source']}")
        lines.append(f"- **Summary:** {r['summary']}")
        lines.append("- **Feature sequence:**")
        for i, step in enumerate(r["feature_sequence"], 1):
            lines.append(f"  {i}. {step}")
        lines.append("- **Design intent:**")
        for di in r["design_intent"]:
            lines.append(f"  - {di}")
        lines.append("- **Key dimensions:**")
        for kd in r["key_dimensions"]:
            lines.append(f"  - {kd}")
        lines.append("")

    lines.append("## GD&T reference")
    lines.append("")
    lines.append(GDNT["summary"])
    lines.append("")
    lines.append("**Categories**")
    for k, v in GDNT["categories"].items():
        lines.append(f"- **{k}:** {v}")
    lines.append("")
    lines.append(f"**Datums** — {GDNT['datums']}")
    lines.append("")
    lines.append(f"**Modifiers** — {GDNT['modifiers']}")
    lines.append("")
    lines.append("**Rules of thumb**")
    for rt in GDNT["rules_of_thumb"]:
        lines.append(f"- {rt}")
    lines.append("")
    return "\n".join(lines)


def write_playbook() -> str:
    PLAYBOOK_FILE.parent.mkdir(parents=True, exist_ok=True)
    md = render_playbook_md()
    PLAYBOOK_FILE.write_text(md, encoding="utf-8")
    return str(PLAYBOOK_FILE)
