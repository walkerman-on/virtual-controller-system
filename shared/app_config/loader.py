"""Загрузка config.json без автодополнения: все обязательные секции задаются в файле."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_app_config(path: str | Path) -> dict[str, Any]:
    """Прочитать JSON-конфигурацию с диска."""
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)
