"""Capability guardrails for tool-level system access.

Normal mode keeps tool actions scoped to safer locations.
God mode broadens Linux/Arch access while still blocking Windows/ASUS paths.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

import config


MODE_FILE = config.DATA_DIR / "identity" / "capability_mode.json"
AUDIT_LOG = config.LOGS_DIR / "god_mode_actions.log"


@dataclass
class CapabilityDecision:
    allowed: bool
    reason: str


class CapabilityGuard:
    def __init__(self) -> None:
        self.mode = "normal"
        self._deny_markers = [
            "/mnt/win_c",
            "\\\\windows\\",
            "/windows/",
            "program files",
            "program files (x86)",
            "asus",
        ]
        self._load_mode()

    def enable_god_mode(self) -> str:
        self.mode = "god"
        self._save_mode()
        logger.warning("Capability mode switched to GOD")
        return "god mode enabled"

    def disable_god_mode(self) -> str:
        self.mode = "normal"
        self._save_mode()
        return "god mode disabled"

    def status(self) -> str:
        if self.mode == "god":
            return "god mode is ON (Linux/Arch access widened; Windows/ASUS paths blocked)"
        return "god mode is OFF (safe scoped access)"

    def scope(self) -> str:
        if self.mode == "god":
            return "scope: broad Linux/Arch filesystem and shell access, minus Windows/ASUS-denied paths"
        return "scope: workspace/home/tmp-oriented access only"

    def check_path(self, path_text: str) -> CapabilityDecision:
        low = path_text.strip().lower()
        if self._contains_denied_marker(low):
            return CapabilityDecision(False, "blocked: Windows/ASUS path is denied")

        if self.mode == "god":
            return CapabilityDecision(True, "allowed")

        p = Path(path_text).expanduser()
        allowed_roots = [
            str(config.BASE_DIR.resolve()),
            str(Path.home().resolve()),
            "/tmp",
            "/var/tmp",
        ]

        candidate = str(p)
        if p.is_absolute():
            try:
                candidate = str(p.resolve(strict=False))
            except Exception:
                candidate = str(p)

        if any(candidate.startswith(root) for root in allowed_roots):
            return CapabilityDecision(True, "allowed")

        return CapabilityDecision(False, "blocked: path outside normal-mode scope")

    def check_command(self, cmd: str) -> CapabilityDecision:
        low = cmd.lower()
        hard_block = ["mkfs", "dd if=", ":(){", "fork bomb", "rm -rf /"]
        if any(token in low for token in hard_block):
            return CapabilityDecision(False, "blocked: destructive command signature")

        if self._contains_denied_marker(low):
            return CapabilityDecision(False, "blocked: Windows/ASUS target in command")

        if self.mode == "god":
            return CapabilityDecision(True, "allowed")

        if any(tok in low for tok in ["systemctl", "pacman", "yay", "sudo", "chmod", "chown"]):
            return CapabilityDecision(False, "blocked: elevated/system command in normal mode")

        return CapabilityDecision(True, "allowed")

    def audit(self, action: str, target: str) -> None:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"action": action, "target": target, "mode": self.mode}, ensure_ascii=True)
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _contains_denied_marker(self, text: str) -> bool:
        return any(marker in text for marker in self._deny_markers)

    def _load_mode(self) -> None:
        try:
            if MODE_FILE.exists():
                data = json.loads(MODE_FILE.read_text(encoding="utf-8"))
                mode = str(data.get("mode", "normal")).lower().strip()
                self.mode = "god" if mode == "god" else "normal"
        except Exception as e:
            logger.warning(f"Failed to load capability mode: {e}")
            self.mode = "normal"

    def _save_mode(self) -> None:
        MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
        MODE_FILE.write_text(json.dumps({"mode": self.mode}, indent=2), encoding="utf-8")


capability_guard = CapabilityGuard()
