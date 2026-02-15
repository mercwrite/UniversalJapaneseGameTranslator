"""User preferences persistence for settings that survive across sessions."""

from __future__ import annotations

import json
import os
from typing import Any


# Default file location: next to the script
_DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_preferences.json")

_DEFAULTS: dict[str, Any] = {
    "engine_type": 0,           # EngineType.LIGHTWEIGHT
    "pipeline_interval": 100,   # ms
    "preprocess_by_engine": {   # str(EngineType value) -> bool
        "0": True,
        "1": False,
    },
    "preprocessing_pipeline": None,  # None means use defaults
}


class Preferences:
    """Load / save a flat JSON preferences file."""

    def __init__(self, path: str = _DEFAULT_PATH):
        self._path = path
        self._data: dict[str, Any] = dict(_DEFAULTS)
        self.load()

    # ── public getters / setters ──

    @property
    def engine_type(self) -> int:
        return self._data.get("engine_type", _DEFAULTS["engine_type"])

    @engine_type.setter
    def engine_type(self, value: int) -> None:
        self._data["engine_type"] = value
        self.save()

    @property
    def pipeline_interval(self) -> int:
        return self._data.get("pipeline_interval", _DEFAULTS["pipeline_interval"])

    @pipeline_interval.setter
    def pipeline_interval(self, value: int) -> None:
        self._data["pipeline_interval"] = value
        self.save()

    @property
    def preprocess_by_engine(self) -> dict[str, bool]:
        return self._data.get("preprocess_by_engine", _DEFAULTS["preprocess_by_engine"])

    @preprocess_by_engine.setter
    def preprocess_by_engine(self, value: dict[str, bool]) -> None:
        self._data["preprocess_by_engine"] = value
        self.save()

    def get_preprocess_for_engine(self, engine_type_value: int) -> bool | None:
        """Get preprocessing toggle for a specific engine type. Returns None if not set."""
        return self.preprocess_by_engine.get(str(engine_type_value))

    def set_preprocess_for_engine(self, engine_type_value: int, enabled: bool) -> None:
        prefs = self.preprocess_by_engine
        prefs[str(engine_type_value)] = enabled
        self.preprocess_by_engine = prefs  # triggers save

    @property
    def preprocessing_pipeline(self) -> list[dict] | None:
        return self._data.get("preprocessing_pipeline")

    @preprocessing_pipeline.setter
    def preprocessing_pipeline(self, value: list[dict] | None) -> None:
        self._data["preprocessing_pipeline"] = value
        self.save()

    # ── persistence ──

    def load(self) -> None:
        """Load preferences from disk. Missing keys get defaults."""
        if not os.path.isfile(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                for key in _DEFAULTS:
                    if key in stored:
                        self._data[key] = stored[key]
        except Exception as e:
            print(f"Warning: Failed to load preferences: {e}")

    def save(self) -> None:
        """Persist current preferences to disk."""
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Failed to save preferences: {e}")
