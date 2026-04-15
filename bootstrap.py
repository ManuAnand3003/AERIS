"""AERIS bootstrap and preflight helper.

This prepares local folders, reports missing runtime pieces, and keeps model installation separate.
"""

from pathlib import Path
import sys

import config


def ensure_directories() -> None:
    for path in [config.DATA_DIR, config.CONVERSATIONS_DIR, config.MEMORY_DB_DIR, config.IDENTITY_DIR, config.LOGS_DIR, config.TOOLS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def report_paths() -> None:
    print("AERIS bootstrap status")
    print(f"  data: {config.DATA_DIR}")
    print(f"  models: {config.MODELS_DIR}")
    print(f"  memory db: {config.MEMORY_DB_DIR}")
    print(f"  identity: {config.IDENTITY_DIR}")
    print(f"  logs: {config.LOGS_DIR}")


def report_model_presence() -> None:
    available = []
    missing = []
    for name, model_cfg in config.MODELS.items():
        if model_cfg["path"].exists():
            available.append(name)
        else:
            missing.append(name)

    print(f"  models present: {len(available)}")
    print(f"  models missing: {len(missing)}")
    if missing:
        print("  first missing models:")
        for name in missing[:5]:
            print(f"    - {name}")


def main() -> int:
    ensure_directories()
    report_paths()
    report_model_presence()
    print("\nBootstrap complete. No models were installed or downloaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())