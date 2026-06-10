from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def load_config(path: str | Path) -> Dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    project_root = config_path.resolve().parents[1]
    config["_paths"] = {
        "project_root": str(project_root),
        "config_path": str(config_path.resolve()),
    }
    return config


def project_path(config: Dict[str, Any], *parts: str) -> Path:
    return Path(config["_paths"]["project_root"]).joinpath(*parts)
