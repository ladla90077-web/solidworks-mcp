"""Spike 1: prove COM connection + version, and probe macro-execution surface.

Run:  python scripts/spike_connect.py
This will LAUNCH SolidWorks 2022 if it is not already running (~1 min).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sw_mcp.sw_connection import SWConnection  # noqa: E402


def main() -> None:
    conn = SWConnection.get()
    print("Connecting to SolidWorks (launching if needed)...", flush=True)
    app = conn.ensure(launch=True, visible=True)
    print("CONNECTED.", flush=True)
    print("INFO:", conn.info(), flush=True)

    # Probe which macro / VBA related members this build exposes (late-bound,
    # so we just check by attribute access on the dispatch wrapper).
    candidates = [
        "RunMacro2", "RunMacro", "GetMacroMethods", "SetCurrentMacroPathName",
        "RecordMacro", "StopRecordingMacro2", "EnableMacroRecord",
        "OpenMacro", "CreateNewMacro",
    ]
    print("\n-- macro-related member probe --", flush=True)
    for name in candidates:
        present = hasattr(app, name)
        print(f"  {name:28s}: {'present' if present else 'absent'}", flush=True)


if __name__ == "__main__":
    main()
