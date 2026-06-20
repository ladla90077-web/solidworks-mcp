# Registering the SolidWorks MCP server

## Option A — user scope (available in every project)

```bash
claude mcp add solidworks -s user -- C:/Python313/python.exe -m sw_mcp.server
```

Use the Python interpreter that has the package installed (`pip install -e .`
was run against `C:/Python313/python.exe`). Verify:

```bash
claude mcp list          # expect: solidworks: ... ✓ Connected
claude mcp remove solidworks -s user   # to undo
```

## Option B — project scope (shareable `.mcp.json`)

Create `.mcp.json` in the project root. Teammates who open the project get the
server automatically:

```json
{
  "mcpServers": {
    "solidworks": {
      "command": "C:/Python313/python.exe",
      "args": ["-m", "sw_mcp.server"],
      "env": {}
    }
  }
}
```

If the package is not installed (`pip install -e .`), point at the source
instead by adding `"PYTHONPATH": "C:/Users/lenovo/Desktop/solidworks MCP/src"`
to `env` and keeping the same `args`.

## Option C — console-script entry point

After `pip install -e .` a `solidworks-mcp` launcher is created:

```
C:/Users/lenovo/AppData/Roaming/Python/Python313/Scripts/solidworks-mcp.exe
```

```bash
claude mcp add solidworks -s user -- C:/Users/lenovo/AppData/Roaming/Python/Python313/Scripts/solidworks-mcp.exe
```

## First-run checklist

1. SolidWorks 2022 installed; default templates set (Tools ▸ Options ▸ Default
   Templates). The server will launch SolidWorks on the first tool call if it
   is not already running.
2. `python -m playwright install chromium` has been run once (for the docs
   pipeline).
3. In a fresh Claude session, call `sw_status` — it should report
   `revision: "30.1.0", year: 2022`.

## Tools that change state

`new_document`, `create_extrusion`, `create_cylinder`, `run_macro`, `run_vba`
and `run_and_verify` create/modify documents in SolidWorks. `save_model` /
`export_file` write files. Everything else (status, diagnostics, mass/bbox,
screenshot, docs lookups) is read-only.
