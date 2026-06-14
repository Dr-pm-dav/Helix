"""Configuration helpers for local Helix workflows."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    api_key: str
    project_root: Path
    data_dir: Path
    output_dir: Path


def load_local_env(project_root: Path) -> None:
    env_path = project_root / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip())


def load_settings(project_root: Path | None = None) -> Settings:
    root = project_root or Path(__file__).resolve().parents[2]
    load_local_env(root)
    api_key = os.getenv("EIA_API_KEY")
    if not api_key:
        raise RuntimeError("Missing EIA_API_KEY. Add it to .env or the environment.")
    return Settings(
        api_key=api_key,
        project_root=root,
        data_dir=root / "data",
        output_dir=root / "outputs",
    )

