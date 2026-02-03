from __future__ import annotations
import os
import json
from pathlib import Path
from typing import Any, Dict

import yaml

def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)

def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)

def project_root_from_script() -> str:
    # assumes scripts/ is directly under predictive_analytics_module/
    return str(Path(__file__).resolve().parents[1])
