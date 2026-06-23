"""Safe, reversible SOLIDWORKS UI suppression for faster automation."""
from __future__ import annotations

from typing import Any


class fast_mode:
    """Temporarily suppress redraw/tree churn while an API operation runs.

    Every original value is restored in ``__exit__``. Unlike Cosmon's most
    aggressive mode this does not disable the application window, so a crash
    cannot leave SOLIDWORKS input-locked.
    """

    def __init__(self, app: Any, enabled: bool = True) -> None:
        self.app = app
        self.enabled = enabled
        self.saved: list[tuple[Any, str, Any]] = []

    def _set(self, obj: Any, name: str, value: Any) -> None:
        if obj is None:
            return
        try:
            old = getattr(obj, name)
            old = old() if callable(old) else old
            self.saved.append((obj, name, old))
            setattr(obj, name, value)
        except Exception:  # noqa: BLE001 - optimization must never block work
            pass

    def __enter__(self):
        if not self.enabled:
            return self
        self._set(self.app, "CommandInProgress", True)
        try:
            doc = self.app.ActiveDoc
        except Exception:  # noqa: BLE001
            doc = None
        if doc is not None:
            try:
                self._set(doc.ActiveView, "EnableGraphicsUpdate", False)
            except Exception:  # noqa: BLE001
                pass
            try:
                self._set(doc.FeatureManager, "EnableFeatureTree", False)
            except Exception:  # noqa: BLE001
                pass
            try:
                self._set(doc.SketchManager, "DisplayWhenAdded", False)
            except Exception:  # noqa: BLE001
                pass
        return self

    def __exit__(self, *_exc) -> None:
        for obj, name, old in reversed(self.saved):
            try:
                setattr(obj, name, old)
            except Exception:  # noqa: BLE001
                pass
        self.saved.clear()
