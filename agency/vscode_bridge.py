"""Approval-gated bridge for VS Code-oriented actions."""

from __future__ import annotations

import subprocess
from pathlib import Path
import shutil

import config


class VSCodeBridge:
    def __init__(self) -> None:
        self._code_bin = shutil.which("code") or shutil.which("codium")

    def available(self) -> bool:
        return self._code_bin is not None

    def open_file(self, path: str, line: int | None = None) -> str:
        if not self.available():
            return "VS Code CLI not found (expected 'code' or 'codium')."

        p = Path(path).expanduser()
        target = str(p)
        if line and line > 0:
            target = f"{target}:{line}"
            cmd = [self._code_bin, "-g", target]
        else:
            cmd = [self._code_bin, "--reuse-window", target]
        subprocess.run(cmd, check=False)
        return f"Opened in VS Code: {target}"

    def patch_file(self, path: str, old_text: str, new_text: str) -> str:
        p = Path(path).expanduser()
        if not p.exists():
            return f"File not found: {p}"
        content = p.read_text(encoding="utf-8")
        if old_text not in content:
            return "Patch target text not found."
        updated = content.replace(old_text, new_text, 1)
        p.write_text(updated, encoding="utf-8")
        return f"Patched file: {p}"

    def run_task(self, command: str) -> str:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(config.BASE_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = (result.stdout + result.stderr).strip()
        if not output:
            output = "(no output)"
        return output[:4000]


vscode_bridge = VSCodeBridge()
