# SolidWorks MCP — session rules

This repo is a SolidWorks 2022 MCP server (`src/sw_mcp`). When the user
describes a part, shows a picture, or asks to make anything mechanical,
**start building immediately** — do not ask clarifying questions first.

## Automatic workflow (every part request)

1. `prepare_modeling_context(request)` — auto-detects/selects the running
   SolidWorks session. Only stop if it reports `start_solidworks` (ask the
   user to open SolidWorks) or `select_session` (ask which PID).
2. `api_map(...)` / `docs_lookup_batch(...)` — fetch ALL needed signatures,
   accessor chains and enum tables in one or two calls. Never one lookup per
   method; never read the CHM cache or big JSON resources directly.
3. Generate ONE complete macro and run it with `run_and_verify`. It statically
   lints first (`static_check` failures come back in milliseconds — fix those
   before any rerun). Iterate on the verdict until `success: true`.
4. `capture_screenshot` and show the user the result.
5. If a fix wasn't already in `suggested_fixes`, record it with `learn_rule`.

Pick sensible engineering defaults for unstated dimensions and say what you
chose — do not block on questions.

## Quality bar (non-negotiable)

Never deliver a bare block or cylinder. Every part gets:

- **Edge finishing on ALL edges**: fillets on external/cosmetic edges,
  chamfers on hole entries and lead-ins (`FeatureFillet3`,
  `InsertFeatureChamfer`) as a finishing pass before the final rebuild.
- Real design intent: Hole Wizard holes (not plain cuts), bolt circles,
  draft on molded bosses, sane wall thicknesses.
- Use `get_design_guidance` recipes for the archetype (bearing, plate,
  manifold, bracket) so proportions are engineering-informed.
- Verify visually with a screenshot; if any edge is still sharp, add the
  missing fillet/chamfer and rerun.

## Repo notes

- Docs are retrieval-based: CHM index + FTS5 (`local_docs.py`) and keyed
  Cosmon databases (`cosmon_db.py`, 0.18s lazy load). Web rendering only on
  explicit `prefer='web'`.
- Keep tool payloads compact — the latency budget is round trips × context
  size, not server compute.
- Tests: `python -m pytest tests -q`. COM tests skip without a live
  SolidWorks; pure tests must never depend on the `sw` fixture.
