"""Spike 4: end-to-end heart test.
Generate an extrude part (verified style) -> run inline -> read log -> rebuild
-> diagnostics -> verdict. SolidWorks must be running.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sw_mcp import executor, feature_tools  # noqa: E402
from sw_mcp.com_worker import call  # noqa: E402
from sw_mcp.util import new_work_path  # noqa: E402


def main():
    log_path = str(new_work_path(".log"))
    code = feature_tools.build_extrusion(length_mm=80, width_mm=50, height_mm=12,
                                         plane=2, log_path=log_path)
    print("=== generated VBA (first 600 chars) ===")
    print(code[:600])
    print("...\n")
    verdict = call(lambda app: executor.run_inline_and_verify(app, code, log_path=log_path))
    print("=== VERDICT ===")
    print(json.dumps(verdict, indent=2, default=str))


if __name__ == "__main__":
    main()
