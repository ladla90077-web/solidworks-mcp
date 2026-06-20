"""Quick harness: build a feature macro and run+verify it.
Usage: python scripts/try_feature.py <builder> [args...]
e.g.   python scripts/try_feature.py build_fillet 120 80 40 6
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sw_mcp import executor, feature_tools  # noqa: E402
from sw_mcp.com_worker import call  # noqa: E402
from sw_mcp.util import new_work_path  # noqa: E402


def main():
    def _coerce(a):
        try:
            return float(a)
        except ValueError:
            return a

    name = sys.argv[1]
    args = [_coerce(a) for a in sys.argv[2:]]
    builder = getattr(feature_tools, name)
    log_path = str(new_work_path(".log"))
    code = builder(*args, log_path=log_path)
    verdict = call(lambda app: executor.run_inline_and_verify(app, code, log_path=log_path))
    print(f"=== {name}{tuple(args)} ===")
    print("SUCCESS:", verdict["success"], "| ran:", verdict["ran"],
          "| has_errors:", verdict["has_errors"], "| features:", verdict["feature_count"])
    for s in verdict["log"]:
        print("  ", s["status"], s["step"], "-", s["message"])
    if not verdict["success"]:
        if verdict.get("suggested_fixes"):
            print("SUGGESTED FIXES:")
            for f in verdict["suggested_fixes"]:
                print("   *", f["title"], "->", f["fix"][:80])
        print("macro_path:", verdict.get("macro_path"))


if __name__ == "__main__":
    main()
