# SolidWorks MCP — run, test & auto-fix VBA macros

An MCP server that connects to a running **SolidWorks 2022** over COM (pywin32),
runs your VBA macros (or inline VBA), inspects the resulting model, and returns
**structured diagnostics** so Claude can fix errors and re-run until the model
builds clean. It also ships an **API-documentation pipeline** that renders the
JavaScript-only `help.solidworks.com/2022` pages headlessly and extracts the
method/enum facts that keep generated code correct.

Built to pair with the `solidworks-vba` skill: the skill *writes* verified-style
macros; this server *runs, tests and repairs* them.

## How it works

```
Claude (+ solidworks-vba skill)
        │  writes / fixes VBA
        ▼
  run_and_verify ──► COM worker thread (STA) ──► SolidWorks 2022
        │                                              │
        │   ◄── verdict: ran? rebuild errors?  ◄───────┘
        ▼        errored features? VBA error?
   if not success: read errors, regenerate, call again   (Claude-driven loop)
```

- **Inline VBA** is written to a temporary `.swb` and executed with `RunMacro2`
  (SolidWorks compiles `.swb` text on the fly — no `.swp` authoring, no VBA
  trust-access setting needed).
- All COM access runs on **one STA worker thread** (COM objects are
  apartment-bound).
- Generated/automated macros use a **silent log** (`SWMCP_Log`) instead of
  `MsgBox`, and a **dialog watchdog** auto-dismisses stray modal dialogs so a
  macro can never deadlock the server.
- The server never edits your VBA. It returns rich errors; Claude fixes them.

## Session-first fast workflow

Every modeling request should begin with `prepare_modeling_context(request)`.
It performs the complete preflight in one round trip:

1. Detect running SOLIDWORKS processes through their exact ROT monikers.
2. Auto-select the only session, or return the process list when a choice is required.
3. Stop with `action=start_solidworks` when no session is running—nothing is launched silently.
4. Return matching skills, professional design guidance, bundled Cosmon references,
   and local SOLIDWORKS CHM results before any code is generated.
5. Bind every subsequent modeling tool to the selected process.

`sw_list_sessions`, `sw_select_session(process_id)`, and `sw_disconnect_session`
provide explicit control. Execution suppresses graphics/tree churn reversibly,
generated macros rebuild once, verification scans the feature tree once, and
repeated Cosmon searches are served from memory.

## Requirements

- Windows + **SolidWorks 2022** (COM ProgID `SldWorks.Application`).
- **Python 3.10+**.
- A **default part/assembly/drawing template** configured in SolidWorks
  (Tools ▸ Options ▸ Default Templates) — macros abort cleanly if none is set.

## Install

```bash
pip install -e .
python -m playwright install chromium   # one-time, for the docs pipeline
```

## Register with Claude Code

Already registered at user scope during setup:

```bash
claude mcp add solidworks -s user -- C:/Python313/python.exe -m sw_mcp.server
```

Or, for a project-scoped, shareable config, drop a `.mcp.json` in the project
root (see [install/register-mcp.md](install/register-mcp.md)). Confirm with
`claude mcp list` (look for `solidworks: ... ✓ Connected`).

## Tools

**Session and preflight** — `prepare_modeling_context`, `sw_status`,
`sw_list_sessions`, `sw_select_session`, `sw_disconnect_session`

**Professional design knowledge (proactive)**
- `get_design_guidance(query)` — **call this BEFORE modeling.** Returns the
  matching professional *archetype recipe* (ordered feature sequence,
  design-intent practices, key dimensions), the relevant universal design
  principles, and — for tolerancing queries — a GD&T reference. Distilled from
  real SolidWorks tutorials (`transcripts.txt`) so the build tools produce a real
  engineered component instead of a bare block or cylinder.
- `list_design_recipes()` — the available archetypes (bearing, engine, bottle,
  manifold, revolved housing, mounting plate).
  See [`DESIGN_PLAYBOOK.md`](src/sw_mcp/resources/knowledge/DESIGN_PLAYBOOK.md).

**Execute & verify**
- `run_macro(path, module, procedure)` — run an existing `.swp`/`.swb`.
- `run_vba(code, procedure, module)` — run an inline VBA string.
- `run_and_verify(code | macro_path, …)` — run → rebuild → scan → one verdict.
  **The auto-fix-loop primitive.**

**Diagnostics** — `rebuild_model`, `get_build_errors`, `get_feature_tree`,
`get_mass_properties`, `get_bounding_box`, `capture_screenshot`

**Documents** — `new_document`, `open_model`, `save_model`, `close_model`,
`export_file` (STEP/IGES/STL/X_T/PDF/PNG by extension)

**Feature generators** — single-feature *primitives* (verified-style VBA, each
built → run → rebuilt → error-scanned). These are building blocks and smoke
tests, **not** finished parts; a professional component is composed from them
(plus inline `run_vba`) following the recipe from `get_design_guidance`:
`create_extrusion`, `create_cylinder`, `create_fillet`, `create_chamfer`,
`create_shell`, `create_draft`, `create_rib` (L-bracket + gusset),
`create_revolve` (tube), `create_sweep` (swept groove), `create_loft` (lofted cut),
`create_hole_wizard` (metric counterbore), `create_thread` (real cut thread),
`create_spring` (helix + sweep), `create_linear_pattern`, `create_mirror`,
`create_circular_pattern`, `create_assembly` (2 components fully mated).
**Surface modeling:** `create_surface_extrude`, `create_surface_planar`,
`create_surface_revolve`, `create_surface_thicken` (surface→solid).
**Sheet metal:** `create_sheet_base_flange` (flat plate), `create_sheet_lbracket`
(bent, real bend). Extend by adding builders to `feature_tools.py` (see below).
Pattern variants not yet given a one-call tool (curve/sketch/table/fill), sheet-metal
edge flange/hem/miter, and any other feature are fully buildable via `run_vba` + the
`solidworks-vba` skill + the auto-fix loop.

**Self-improving knowledge base** — `learn_rule`, `list_rules`. Every fixed error
becomes a persistent rule (`resources/knowledge/rules.json`, human-readable
`LESSONS.md`). On failure, `run_and_verify` returns `suggested_fixes` matched from
past rules, so the same mistake is never solved twice.

**API docs** — `docs_lookup_method(interface, method)`,
`docs_lookup_enum(enum_name)`, `docs_get(url)`. Read the `remarks` field — it
holds the selection-mark/precondition details that separate working from
crashing code.

**Cosmon-compatible resources and skills** —
`engineering_resources_status`, `list_engineering_resources`,
`search_engineering_resources`, `get_engineering_resource`, `list_skills`,
`get_skill`, `create_skill`, `update_skill`, `delete_skill`, `import_skill`.
The server bundles Cosmon's complete SOLIDWORKS documentation payload—including
the large feature/function databases—plus C# templates, persistent-service
source, and all 12 packaged skills. The installed Cosmon resources remain a
fallback source. Set `COSMON_RESOURCES_DIR` for a non-default Cosmon location
and `SW_MCP_SKILLS_DIR` for editable skill overrides.

## The auto-fix loop

1. Claude writes a macro (via the `solidworks-vba` skill) and calls
   `run_and_verify`.
2. The verdict comes back: `{success, ran, run_error, log[], log_errors[],
   errors[], errored_features[], suppressed_features[], feature_count}`.
3. If `success == false`, Claude reads `log_errors`/`errors` (and looks up the
   exact API via `docs_lookup_method`), regenerates the corrected VBA, and calls
   `run_and_verify` again — until `success == true`.

## Designing professional parts (not bare blocks)

The build loop only checks that geometry *rebuilds* — left alone, the simplest
shape that builds clean is a block or a cylinder. To get a real engineered
component, design intent has to come from somewhere. That is the
`get_design_guidance` layer (`design_library.py`, surfaced from the tutorial
transcripts):

1. Call `get_design_guidance("<part description>")` (e.g. `"deep-groove ball
   bearing"`, `"mounting base plate with bolt circle"`, `"hollow exhaust
   manifold"`, `"shaft tolerance / GD&T"`).
2. Follow the returned **feature sequence** and **design-intent** notes — revolve
   about a centerline, fully-define sketches, locate holes on a construction PCD
   and circular-pattern them, break every edge, surface-then-thicken for
   thin-wall parts, combine-then-shell for hollow ones, fix-first then
   fully-constrain for assemblies, apply GD&T to functional features.
3. Emit the VBA (the feature primitives below, or inline `run_vba`) and drive it
   through `run_and_verify` until `success == true`.

The recipes are an *index of archetypes*; the **principles** apply to every part.
The same knowledge is mirrored as reactive rules in `rules.json`, so a related
build error also surfaces the relevant professional practice as a
`suggested_fix`.

## Writing more feature generators

Generators emit VBA in the verified `solidworks-vba` style and run through
`run_and_verify`. Two **non-negotiable rules** for inline `.swb` code (learned
the hard way — see `src/sw_mcp/vba/helpers.vba`):

1. **Never test an API boolean with bitwise `If Not x`.** In an on-the-fly
   `.swb`, API `VARIANT_BOOL` returns arrive as `+1`, and VBA's `Not` is
   bitwise (`Not 1 = -2`, truthy). Always write `If x = False Then`. Object
   checks (`Is Nothing`) are fine.
2. **`Create*Rectangle` returns a Variant array, not an object.** Capture with
   `Dim v As Variant: v = ...` and check `IsArray(v)` — never `Set seg = …`
   (raises run-time error 424).

Add a `build_<feature>()` to `feature_tools.py` (reuse `assemble_part_macro`)
and a thin `@mcp.tool()` wrapper in `server.py`.

## Diagnostic scripts

`scripts/` contains the standalone spikes used to validate each layer
(`spike_connect`, `spike_runmacro`, `spike_build`, `spike_autofix`, …). They are
handy for debugging the COM link without going through the MCP transport.
