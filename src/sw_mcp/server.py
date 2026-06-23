"""SolidWorks 2022 MCP server.

Exposes tools to run, test and auto-fix VBA macros in a running SolidWorks
instance, inspect the resulting model, and look up the JS-rendered SolidWorks
API documentation. All SolidWorks COM access is funnelled through one STA
worker thread (com_worker); the docs pipeline runs in-process.

The auto-fix loop is Claude-driven: tools return rich structured diagnostics
and Claude regenerates corrected VBA (with the solidworks-vba skill) and calls
run_and_verify again until `success` is true.
"""
from __future__ import annotations

import re
import time
from typing import Optional

from mcp.server.fastmcp import FastMCP

from . import (cosmon_resources, design_library, diagnostics, docs_pipeline,
               executor, feature_tools, knowledge, model_ops, skills)
from .com_worker import call
from .sw_connection import SWConnection
from .util import new_work_path

mcp = FastMCP(
    "solidworks",
    instructions=(
        "Operate as a session-first engineering-aware SOLIDWORKS agent. Start every modeling "
        "request with prepare_modeling_context. If it reports start_solidworks, ask the user "
        "to open SOLIDWORKS; if it reports select_session, ask them to choose one of the listed "
        "process IDs and call sw_select_session. Never model against an unselected process. "
        "Use bundled Cosmon references and local CHM documentation before generating code or "
        "using the web. Load the matched skill and design guidance returned by the context tool. "
        "Execute through run_and_verify, inspect the structured verdict, correct failures, and "
        "repeat until success. Record genuinely new "
        "fixes with learn_rule. Prefer explicit dimensions, design intent, manufacturability, "
        "and shop-ready drawings over visually plausible but under-defined geometry."
    ),
)


# === Connection ============================================================
@mcp.tool()
def sw_status() -> dict:
    """Report the selected SOLIDWORKS session without launching the application.
    A sole running session is selected automatically; zero sessions returns
    action=start_solidworks, and multiple sessions returns action=select_session."""
    return call(lambda: SWConnection.get().session_status(), needs_app=False)


@mcp.tool()
def sw_list_sessions() -> dict:
    """List every running SOLIDWORKS ROT session with process ID, version and
    active document. This never launches SOLIDWORKS or changes the selection."""
    sessions = call(lambda: SWConnection.get().list_sessions(), needs_app=False)
    return {"sessions": sessions, "count": len(sessions)}


@mcp.tool()
def sw_select_session(process_id: int) -> dict:
    """Bind all subsequent MCP geometry operations to one exact running
    SOLIDWORKS process. Required when more than one session is running."""
    return call(lambda: SWConnection.get().select_session(process_id), needs_app=False)


@mcp.tool()
def sw_disconnect_session() -> dict:
    """Release the MCP's session selection without closing SOLIDWORKS."""
    return call(lambda: SWConnection.get().clear_selection(), needs_app=False)


def _matching_skills(query: str, limit: int = 4) -> list[dict]:
    terms = set(re.findall(r"[a-z0-9]+", query.casefold()))
    ranked = []
    for item in skills.list_skills():
        haystack = f"{item['slug']} {item['name']} {item['description']}".casefold()
        score = sum(1 for term in terms if term in haystack)
        if score:
            ranked.append((score, item))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["name"]))
    return [item for _, item in ranked[:limit]]


@mcp.tool()
def prepare_modeling_context(request: str, process_id: int = 0,
                             reference_limit: int = 8) -> dict:
    """THE fast session-first preflight. Call once before generating geometry.
    It selects the requested process (or auto-selects the sole session), blocks
    safely with an actionable response when no/ambiguous sessions exist, and
    returns matching skills, professional design guidance, bundled Cosmon/local
    documentation hits, plus the required execution workflow in one round trip."""
    started = time.perf_counter()
    conn = SWConnection.get()
    if process_id:
        call(lambda: conn.select_session(process_id), needs_app=False)
    session = call(lambda: conn.session_status(), needs_app=False)
    if not session.get("ready"):
        return {
            "ready": False,
            "session": session,
            "action": session.get("action"),
            "message": session.get("message"),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        }

    references = cosmon_resources.search(request, "all", reference_limit)
    try:
        from . import local_docs
        local = local_docs.search(request, limit=min(reference_limit, 8))
    except Exception as exc:  # noqa: BLE001
        local = {"available": False, "hits": [], "error": str(exc)}
    matched = _matching_skills(request)
    return {
        "ready": True,
        "session": session,
        "matched_skills": matched,
        "design_guidance": design_library.get_guidance(request),
        "documentation": {
            "priority": ["bundled-cosmon", "local-solidworks-chm", "web-fallback"],
            "cosmon": references,
            "local": local,
        },
        "workflow": [
            "Load the most relevant matched skill with get_skill.",
            "Use the returned design guidance and documentation before writing code.",
            "Generate the complete feature sequence for the selected session.",
            "Execute once with run_and_verify; repair only if its verdict fails.",
        ],
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
    }


# === Macro execution & verification ========================================
@mcp.tool()
def run_macro(path: str, module: str = "", procedure: str = "main") -> dict:
    """Run an existing SolidWorks macro (.swp or .swb) and return a verdict
    with run status, rebuild errors and the errored/suppressed feature lists.
    Use for the user's own saved macros."""
    return call(lambda app: executor.run_file_and_verify(app, path, module, procedure))


@mcp.tool()
def run_vba(code: str, procedure: str = "main", module: str = "Module1") -> dict:
    """Run an inline VBA macro string. The code is written to a temp .swb and
    executed (SolidWorks compiles .swb on the fly). Returns ran/error info and
    the generated macro path. Prefer run_and_verify for the fix loop.

    Generator rules for reliable inline VBA: declare Option Explicit, use the
    SWMCP_Log silent-log convention instead of MsgBox, test API booleans with
    '= False' (never bitwise 'If Not'), and capture Create*Rectangle results as
    a Variant array (not Set)."""
    return call(lambda app: executor.run_inline_and_verify(app, code, proc=procedure,
                                                           module=module, rebuild=True))


@mcp.tool()
def run_and_verify(code: str = "", macro_path: str = "", procedure: str = "main",
                   module: str = "Module1") -> dict:
    """THE auto-fix-loop primitive. Run inline `code` OR an existing `macro_path`,
    rebuild, scan for errors, and return one verdict:
    {success, ran, run_error, log[], log_errors[], errors[], errored_features[],
     suppressed_features[], feature_count, macro_path}.
    On success==false the verdict also includes `suggested_fixes` (previously
    learned rules that match this error) and a `hint`. Apply a suggested fix and
    call again. If you fix a NEW error not already covered, call `learn_rule` so
    it is auto-suggested next time (the server is self-improving)."""
    if macro_path:
        return call(lambda app: executor.run_file_and_verify(app, macro_path,
                                                             module, procedure))
    if not code:
        return {"success": False, "error": "provide either code or macro_path"}
    return call(lambda app: executor.run_inline_and_verify(app, code, proc=procedure,
                                                           module=module, rebuild=True))


# === Professional design knowledge (proactive) ============================
@mcp.tool()
def get_design_guidance(query: str = "") -> dict:
    """Consult this BEFORE modeling so the build tools (run_and_verify, create_*)
    produce a real engineered component instead of a bare block or cylinder.

    Pass a part description or topic (e.g. 'deep-groove ball bearing',
    'mounting base plate with bolt circle', 'hollow exhaust manifold',
    'thin-wall bottle', 'shaft tolerance / GD&T'). Returns the matching
    professional archetype recipe(s) — ordered feature sequence, design-intent
    practices and key dimensions — plus the relevant universal design principles
    (and the GD&T reference for tolerancing queries). Distilled from real
    SolidWorks tutorials. With an empty query it returns the full principle set
    and the recipe index. Use the returned feature sequence to drive the VBA you
    send to run_and_verify."""
    return design_library.get_guidance(query)


@mcp.tool()
def list_design_recipes() -> dict:
    """List the professional archetype recipes available via get_design_guidance
    (name, archetype, keywords, one-line summary, source tutorial)."""
    return {"recipes": design_library.list_recipes()}


# === Engineering resources and skills =====================================
@mcp.tool()
def engineering_resources_status() -> dict:
    """Inventory the Cosmon-derived SOLIDWORKS resource layer: portable guides,
    quick references, feature/function databases, C# execution templates and
    persistent-service source. Also reports whether the full Cosmon installation
    is connected. Set COSMON_RESOURCES_DIR to override its location."""
    result = cosmon_resources.status()
    result["skills"] = {"count": len(skills.list_skills()), "items": skills.list_skills()}
    return result


@mcp.tool()
def list_engineering_resources(collection: str = "all", limit: int = 500) -> dict:
    """List SOLIDWORKS reference resources. collection: all, guides, quickrefs,
    feature_docs, function_docs, service, or code_execution. The returned
    logical paths can be passed to get_engineering_resource."""
    return cosmon_resources.list_resources(collection, limit)


@mcp.tool()
def search_engineering_resources(query: str, collection: str = "all", limit: int = 8) -> dict:
    """Search the full Cosmon SOLIDWORKS knowledge payload, including its large
    feature/function JSON databases and the bundled programming guides. Use
    this before writing unfamiliar geometry, drawing, selection, or API code.
    collection: all, guides, quickrefs, feature_docs, function_docs, service,
    or code_execution."""
    return cosmon_resources.search(query, collection, limit)


@mcp.tool()
def get_engineering_resource(path: str, max_chars: int = 30000) -> dict:
    """Read a resource returned by list/search_engineering_resources. Paths are
    containment checked. Large files are capped; narrow them with search first."""
    return cosmon_resources.get_resource(path, max_chars)


@mcp.tool()
def list_skills() -> dict:
    """List the SOLIDWORKS MCP's available Open Skills. These include Cosmon's
    drawing planning/review, simulation, meshing, Socratic review and document
    skills. Call get_skill before performing a task that matches one."""
    return {"skills": skills.list_skills()}


@mcp.tool()
def get_skill(slug: str) -> dict:
    """Load a skill's full instructions and attachments by slug."""
    return skills.get_skill(slug)


@mcp.tool()
def create_skill(name: str, description: str, instructions: str,
                 metadata: Optional[dict] = None) -> dict:
    """Create a reusable user skill in SW_MCP_SKILLS_DIR. The generated
    SKILL.md follows the same portable convention used by Cosmon."""
    return skills.create_skill(name, description, instructions, metadata)


@mcp.tool()
def update_skill(slug: str, name: str = "", description: Optional[str] = None,
                 instructions: Optional[str] = None, metadata: Optional[dict] = None) -> dict:
    """Update a skill. Editing a bundled skill creates a safe user override and
    never modifies the packaged original."""
    return skills.update_skill(slug, name or None, description, instructions, metadata)


@mcp.tool()
def delete_skill(slug: str, confirm: bool = False) -> dict:
    """Delete an editable user skill. confirm=True is mandatory. Bundled skills
    remain read-only and cannot be removed accidentally."""
    return skills.delete_skill(slug, confirm)


@mcp.tool()
def import_skill(source_path: str) -> dict:
    """Import a directory containing SKILL.md into the user skills library."""
    return skills.import_skill(source_path)


# === Diagnostics ===========================================================
@mcp.tool()
def rebuild_model() -> dict:
    """Force-rebuild the active model (ForceRebuild3) and report per-feature
    error/warning state."""
    return call(lambda app: diagnostics.rebuild(_active(app), force=True))


@mcp.tool()
def get_build_errors() -> dict:
    """List features in the active model that are in an error or warning state
    (via GetWhatsWrong / GetErrorCode2), plus suppressed features."""
    return call(lambda app: diagnostics.get_build_errors(_active(app)))


@mcp.tool()
def get_feature_tree() -> dict:
    """Return the full feature tree of the active model: name, type
    (GetTypeName2), suppressed and error_code for each feature."""
    return call(lambda app: {"features": diagnostics.walk_feature_tree(_active(app))})


# === Document / utility ====================================================
@mcp.tool()
def new_document(doc_type: str = "part") -> dict:
    """Create a new document ('part', 'assembly' or 'drawing') from the user's
    configured default template."""
    return call(lambda app: model_ops.new_document(app, doc_type))


@mcp.tool()
def open_model(path: str, config: str = "") -> dict:
    """Open a .sldprt/.sldasm/.slddrw file and report open errors/warnings."""
    return call(lambda app: model_ops.open_model(app, path, config))


@mcp.tool()
def save_model(path: str = "") -> dict:
    """Save the active document (Save), or Save As if `path` is given."""
    return call(lambda app: model_ops.save_model(app, path or None))


@mcp.tool()
def close_model(save: bool = False) -> dict:
    """Close the active document, optionally saving first."""
    return call(lambda app: model_ops.close_model(app, save))


@mcp.tool()
def export_file(path: str) -> dict:
    """Export the active model to a path; format inferred from the extension
    (.step, .iges, .stl, .x_t, .pdf, .png, ...)."""
    return call(lambda app: model_ops.export_file(app, path))


@mcp.tool()
def get_mass_properties() -> dict:
    """Mass, volume, surface area, density and center of mass of the active model."""
    return call(lambda app: model_ops.get_mass_properties(app))


@mcp.tool()
def get_bounding_box() -> dict:
    """Axis-aligned bounding box (min/max/size, metres) of the active part."""
    return call(lambda app: model_ops.get_bounding_box(app))


@mcp.tool()
def capture_screenshot(path: str = "") -> dict:
    """Save a screenshot (PNG) of the active model's current view and return
    its path."""
    return call(lambda app: model_ops.capture_screenshot(app, path or None))


# === Convenience feature generators (hybrid layer) =========================
@mcp.tool()
def create_extrusion(length_mm: float, width_mm: float, height_mm: float,
                     plane: int = 2) -> dict:
    """Create a new part with a rectangular base extrude (center rectangle ->
    FeatureExtrusion3), built in the verified solidworks-vba style and run +
    verified. plane: 1=Front, 2=Top, 3=Right. Returns the run_and_verify verdict."""
    log_path = str(new_work_path(".log"))
    code = feature_tools.build_extrusion(length_mm, width_mm, height_mm, plane, log_path)
    return call(lambda app: executor.run_inline_and_verify(app, code, log_path=log_path,
                                                           rebuild=False))


@mcp.tool()
def create_cylinder(diameter_mm: float, height_mm: float, plane: int = 2) -> dict:
    """Create a new part with a cylinder (circle sketch -> FeatureExtrusion3),
    built in the verified style and run + verified. plane: 1=Front, 2=Top,
    3=Right. Returns the run_and_verify verdict."""
    log_path = str(new_work_path(".log"))
    code = feature_tools.build_cylinder(diameter_mm, height_mm, plane, log_path)
    return call(lambda app: executor.run_inline_and_verify(app, code, log_path=log_path,
                                                           rebuild=False))


def _run_generated(code: str, log_path: str) -> dict:
    # Generated macros already ForceRebuild once in their footer. Avoid a
    # second full rebuild and verify the resulting tree directly.
    return call(lambda app: executor.run_inline_and_verify(app, code, log_path=log_path,
                                                           rebuild=False))


@mcp.tool()
def create_fillet(length_mm: float, width_mm: float, height_mm: float,
                  radius_mm: float = 6) -> dict:
    """Block + constant-radius edge fillet on the 4 vertical edges (FeatureFillet3)."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_fillet(length_mm, width_mm, height_mm, radius_mm, lp), lp)


@mcp.tool()
def create_chamfer(length_mm: float, width_mm: float, height_mm: float,
                   distance_mm: float = 6) -> dict:
    """Block + 45 degree chamfer on the 4 vertical edges (InsertFeatureChamfer)."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_chamfer(length_mm, width_mm, height_mm, distance_mm, lp), lp)


@mcp.tool()
def create_shell(length_mm: float, width_mm: float, height_mm: float,
                 thickness_mm: float = 5) -> dict:
    """Block shelled to a thin-walled box, removing the top face (InsertFeatureShell)."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_shell(length_mm, width_mm, height_mm, thickness_mm, lp), lp)


@mcp.tool()
def create_draft(length_mm: float, width_mm: float, height_mm: float,
                 angle_deg: float = 5) -> dict:
    """Block + draft applied to the 4 side faces (neutral plane = bottom)."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_draft(length_mm, width_mm, height_mm, angle_deg, lp), lp)


@mcp.tool()
def create_rib(length_mm: float, depth_mm: float, height_mm: float,
               thickness_mm: float = 8) -> dict:
    """L-bracket (plate + perpendicular wall) with a gusset rib bridging the
    inner corner. length=X span, depth=plate reach (+Z), height=wall reach (+Y)."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_rib(length_mm, depth_mm, height_mm, thickness_mm, lp), lp)


@mcp.tool()
def create_revolve(outer_dia_mm: float, inner_dia_mm: float, height_mm: float) -> dict:
    """Revolved tube: a rectangular profile revolved 360 deg about the Y axis
    (FeatureRevolve2). inner_dia_mm=0 gives a solid; >0 gives a hollow tube."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_revolve(outer_dia_mm, inner_dia_mm, height_mm, lp), lp)


@mcp.tool()
def create_sweep(length_mm: float, width_mm: float, height_mm: float,
                 groove_dia_mm: float = 10) -> dict:
    """Block + a swept circular groove cut along the top face (swept cut with a
    circular profile)."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_sweep(length_mm, width_mm, height_mm, groove_dia_mm, lp), lp)


@mcp.tool()
def create_loft(length_mm: float, width_mm: float, height_mm: float,
                depth_mm: float = 30) -> dict:
    """Block + a lofted cut blending a top rectangle to a circle `depth` below
    (two ref planes + InsertCutBlend)."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_loft(length_mm, width_mm, height_mm, depth_mm, lp), lp)


@mcp.tool()
def create_hole_wizard(length_mm: float, width_mm: float, height_mm: float,
                       size: str = "M6", clearance_dia_mm: float = 6.6,
                       counterbore_dia_mm: float = 11, counterbore_depth_mm: float = 6.8) -> dict:
    """Block + a Hole Wizard metric counterbore through the top face (HoleWizard5).
    size is the screw size string, e.g. 'M6'."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_hole_wizard(
        length_mm, width_mm, height_mm, size, clearance_dia_mm,
        counterbore_dia_mm, counterbore_depth_mm, lp), lp)


@mcp.tool()
def create_thread(diameter_mm: float = 20, height_mm: float = 40) -> dict:
    """A cylinder with a real cut Thread feature on its cylindrical face
    (CreateDefinition(swFmSweepThread)). Thread compute can take ~30-60s."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_thread(diameter_mm, height_mm, lp), lp)


@mcp.tool()
def create_spring(coil_dia_mm: float = 40, wire_dia_mm: float = 5,
                  pitch_mm: float = 12, revolutions: float = 6) -> dict:
    """A coil spring: a helix (InsertHelix) swept with a circular wire profile.
    Covers the helix curve and sweep-along-path."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_spring(coil_dia_mm, wire_dia_mm, pitch_mm, revolutions, lp), lp)


@mcp.tool()
def create_linear_pattern(length_mm: float, width_mm: float, height_mm: float,
                          pitch_mm: float = 25, count: int = 5) -> dict:
    """Block + a seed hole linearly patterned along X (swFmLPattern)."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_pattern_linear(
        length_mm, width_mm, height_mm, pitch_mm, count, lp), lp)


@mcp.tool()
def create_mirror(length_mm: float, width_mm: float, height_mm: float) -> dict:
    """Block + a seed hole mirrored about the Right plane (InsertMirrorFeature)."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_pattern_mirror(length_mm, width_mm, height_mm, lp), lp)


@mcp.tool()
def create_circular_pattern(diameter_mm: float = 120, height_mm: float = 15,
                            bolt_circle_mm: float = 80, count: int = 6) -> dict:
    """Disc + central boss + a bolt-circle hole circular-patterned around the
    boss axis (swFmCirPattern)."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_pattern_circular(
        diameter_mm, height_mm, bolt_circle_mm, count, lp), lp)


@mcp.tool()
def create_assembly(offset_mm: float = 80) -> dict:
    """Build a 2-component assembly from scratch: create+save a part, create+save
    an assembly, insert two instances (AddComponent5), and fully constrain both
    with plane mates (AddMate5). Returns the verdict with all mate steps. The
    part/assembly are saved to temp .sldprt/.sldasm files (paths in the log)."""
    lp = str(new_work_path(".log"))
    part_path = str(new_work_path(".sldprt"))
    asm_path = str(new_work_path(".sldasm"))
    code = feature_tools.build_assembly(part_path, asm_path, offset_mm, lp)
    result = _run_generated(code, lp)
    result["part_path"] = part_path
    result["assembly_path"] = asm_path
    return result


# === Surface modeling ======================================================
@mcp.tool()
def create_surface_extrude(length_mm: float = 100, height_mm: float = 40) -> dict:
    """An open line extruded into a flat reference surface (FeatureExtruRefSurface2)."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_surface_extrude(length_mm, height_mm, lp), lp)


@mcp.tool()
def create_surface_planar(length_mm: float = 80, width_mm: float = 50) -> dict:
    """A closed rectangle turned into a planar surface (InsertPlanarRefSurface)."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_surface_planar(length_mm, width_mm, lp), lp)


@mcp.tool()
def create_surface_revolve(radius_mm: float = 25, height_mm: float = 60) -> dict:
    """An open profile + centerline revolved into a surface (InsertRevolvedRefSurface)."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_surface_revolve(radius_mm, height_mm, lp), lp)


@mcp.tool()
def create_surface_thicken(length_mm: float = 100, height_mm: float = 40,
                           thickness_mm: float = 3) -> dict:
    """Pro surface->solid pipeline: extrude a surface, then Thicken it into a solid
    (FeatureBossThicken)."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_surface_thicken(length_mm, height_mm, thickness_mm, lp), lp)


# === Sheet metal ===========================================================
@mcp.tool()
def create_sheet_base_flange(length_mm: float = 120, width_mm: float = 80,
                             thickness_mm: float = 2, bend_radius_mm: float = 1) -> dict:
    """A flat sheet-metal plate from a closed rectangle (InsertSheetMetalBaseFlange2).
    The foundation of every sheet-metal part."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_sheet_base_flange(
        length_mm, width_mm, thickness_mm, bend_radius_mm, lp), lp)


@mcp.tool()
def create_sheet_lbracket(arm1_mm: float = 60, arm2_mm: float = 40, depth_mm: float = 80,
                          thickness_mm: float = 2, bend_radius_mm: float = 2) -> dict:
    """A bent sheet-metal L-bracket from an open L-profile base flange (one feature,
    with a real bend at the corner)."""
    lp = str(new_work_path(".log"))
    return _run_generated(feature_tools.build_sheet_lbracket(
        arm1_mm, arm2_mm, depth_mm, thickness_mm, bend_radius_mm, lp), lp)


# === Self-improving knowledge base =========================================
@mcp.tool()
def learn_rule(title: str, symptom: str = "", cause: str = "", fix: str = "",
               error_signature: str = "", applies_to: Optional[list] = None,
               example_bad: str = "", example_good: str = "") -> dict:
    """Record a lesson so the same error is auto-fixed next time. Call this
    AFTER you diagnose and fix an error that was not already in suggested_fixes.
    `error_signature` is a substring or regex matched (case-insensitive) against
    future error text - make it specific to the failure (e.g. the VBA error
    message or method name). `applies_to` are tags (e.g. ['vba','fillet'])."""
    rule = knowledge.add_rule(title, symptom, cause, fix, error_signature,
                              applies_to, example_bad, example_good)
    return {"recorded": True, "rule": rule}


@mcp.tool()
def list_rules(query: str = "") -> dict:
    """List learned rules (the self-improving knowledge base). With `query`,
    return only rules whose error_signature/tags match it."""
    if query:
        return {"rules": knowledge.match(query, tags=[query])}
    return {"rules": knowledge.all_rules()}


# === API documentation pipeline ============================================
# Local CHM docs are the first-priority source (offline, instant, token-trimmed);
# the JS web render is the fallback for topics not on disk.
@mcp.tool()
def docs_lookup_method(interface: str, method: str, refresh: bool = False,
                       prefer: str = "local") -> dict:
    """Look up a SolidWorks 2022 API method. Reads the installed CHM docs first
    (offline, instant), falling back to the rendered web docs only if the topic
    isn't on disk. e.g. interface='FeatureManager', method='FeatureExtrusion3'.
    Returns syntax, parameters, return value, remarks and example. Read 'remarks'
    - it holds the selection-mark/precondition details that separate working from
    crashing code. prefer='web' forces an online render; refresh=True bypasses
    every cache."""
    return docs_pipeline.lookup_method(interface, method, refresh=refresh,
                                       prefer=prefer)


@mcp.tool()
def docs_lookup_enum(enum_name: str, refresh: bool = False,
                     prefer: str = "local") -> dict:
    """Look up a SolidWorks 2022 enum and its members, e.g. 'swEndConditions_e'.
    Reads local CHM docs first; falls back to the web render if absent."""
    return docs_pipeline.lookup_enum(enum_name, refresh=refresh, prefer=prefer)


@mcp.tool()
def docs_search(query: str, limit: int = 8) -> dict:
    """Full-text search the local SolidWorks API docs (offline, from the CHMs).
    Use this to find the right interface/method/enum by keyword instead of
    guessing in a fix loop - e.g. query='circular pattern feature' or
    'set extrude depth'. Returns lightweight hits (topic stem + title +
    snippet); follow up with docs_lookup_method to read the full topic."""
    from . import local_docs
    return {
        "query": query,
        "priority": ["local-solidworks-chm", "bundled-cosmon", "web-fallback"],
        "local": local_docs.search(query, limit=limit),
        "cosmon": cosmon_resources.search(query, "all", limit),
    }


@mcp.tool()
def docs_status(rebuild: bool = False) -> dict:
    """Report the local CHM docs index (source folder, topic count, readiness)
    and decompile/index them if needed. Pass rebuild=True to re-decompile the
    CHMs from scratch (e.g. after a SolidWorks upgrade)."""
    from . import local_docs
    status = local_docs.ensure_extracted(force=rebuild)
    status["api_dir"] = str(local_docs.api_dir()) if local_docs.api_dir() else None
    status["available"] = local_docs.available()
    return status


@mcp.tool()
def docs_get(url: str, refresh: bool = False) -> dict:
    """Render and scrape any help.solidworks.com/2022 API page by URL (escape
    hatch for pages the method/enum lookups don't cover)."""
    return docs_pipeline.get_page(url, refresh=refresh)


# === helpers ===============================================================
def _active(app):
    doc = app.ActiveDoc
    if doc is None:
        raise RuntimeError("No active document is open in SolidWorks.")
    return doc


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
