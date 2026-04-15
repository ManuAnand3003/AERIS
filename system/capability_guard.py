"""Capability guardrails for tool-level system access.

Normal mode keeps tool actions scoped to safer locations.
God mode broadens Linux/Arch access while still blocking Windows/ASUS paths.
"""

from __future__ import annotations

import json
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from loguru import logger

import config


MODE_FILE = config.DATA_DIR / "identity" / "capability_mode.json"
APPROVALS_FILE = config.DATA_DIR / "identity" / "pending_approvals.json"
GRANTS_FILE = config.DATA_DIR / "identity" / "granted_approvals.json"
AUDIT_LOG = config.LOGS_DIR / "god_mode_actions.log"


@dataclass
class CapabilityDecision:
    allowed: bool
    reason: str
    pending_approval: bool = False
    approval_id: str | None = None


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
        self._high_risk_tokens = [
            "sudo ",
            "systemctl",
            "pacman",
            "yay ",
            "mkinitcpio",
            "grub",
            "iptables",
            "nft ",
            "ufw ",
            "chmod ",
            "chown ",
            "useradd",
            "usermod",
            "passwd",
            "rm -rf",
            "dd if=",
            "mount ",
            "umount ",
        ]
        self._high_risk_path_prefixes = [
            "/etc",
            "/usr",
            "/boot",
            "/var/lib",
            "/opt",
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

    def check_command(self, cmd: str, approval_id: str | None = None) -> CapabilityDecision:
        low = cmd.lower()
        hard_block = ["mkfs", "dd if=", ":(){", "fork bomb", "rm -rf /"]
        if any(token in low for token in hard_block):
            return CapabilityDecision(False, "blocked: destructive command signature")

        if self._contains_denied_marker(low):
            return CapabilityDecision(False, "blocked: Windows/ASUS target in command")

        if self.mode == "god":
            if self._is_high_risk_command(low):
                if approval_id and self.consume_grant(approval_id, "run_shell"):
                    return CapabilityDecision(True, "allowed via approval grant")
                approval_id = self.request_approval("run_shell", cmd, "high-risk system command")
                return CapabilityDecision(
                    False,
                    f"approval required for high-risk command (id: {approval_id})",
                    pending_approval=True,
                    approval_id=approval_id,
                )
            return CapabilityDecision(True, "allowed")

        if any(tok in low for tok in ["systemctl", "pacman", "yay", "sudo", "chmod", "chown"]):
            return CapabilityDecision(False, "blocked: elevated/system command in normal mode")

        return CapabilityDecision(True, "allowed")

    def check_write_path(self, path_text: str, approval_id: str | None = None) -> CapabilityDecision:
        base = self.check_path(path_text)
        if not base.allowed:
            return base

        if self.mode == "god":
            low = path_text.strip().lower()
            if any(low.startswith(prefix) for prefix in self._high_risk_path_prefixes):
                if approval_id and self.consume_grant(approval_id, "write_file"):
                    return CapabilityDecision(True, "allowed via approval grant")
                approval_id = self.request_approval("write_file", path_text, "high-risk system path write")
                return CapabilityDecision(
                    False,
                    f"approval required for high-risk write (id: {approval_id})",
                    pending_approval=True,
                    approval_id=approval_id,
                )

        return CapabilityDecision(True, "allowed")

    def request_approval(self, action: str, target: str, reason: str) -> str:
        approvals = self._read_approvals()
        for existing in approvals:
            if existing.get("action") == action and existing.get("target") == target and existing.get("reason") == reason:
                return str(existing.get("id"))
        approval_id = uuid4().hex[:8]
        approvals.append(
            {
                "id": approval_id,
                "action": action,
                "target": target,
                "reason": reason,
                "created": datetime.now().isoformat(),
            }
        )
        self._write_approvals(approvals)
        self.audit("approval_requested", f"{action}:{approval_id}:{reason}")
        return approval_id

    def list_approvals(self) -> list[dict]:
        return self._read_approvals()

    def approve(self, approval_id: str) -> bool:
        approvals = self._read_approvals()
        selected = next((a for a in approvals if a.get("id") == approval_id), None)
        if selected is None:
            return False
        kept = [a for a in approvals if a.get("id") != approval_id]
        self._write_approvals(kept)

        grants = self._read_grants()
        grants.append(
            {
                "id": selected.get("id"),
                "action": selected.get("action"),
                "target": selected.get("target"),
                "reason": selected.get("reason"),
                "approved": datetime.now().isoformat(),
            }
        )
        self._write_grants(grants)
        self.audit("approval_granted", approval_id)
        return True

    def reject(self, approval_id: str) -> bool:
        approvals = self._read_approvals()
        kept = [a for a in approvals if a.get("id") != approval_id]
        if len(kept) == len(approvals):
            return False
        self._write_approvals(kept)
        self.audit("approval_rejected", approval_id)
        return True

    def consume_grant(self, approval_id: str, action: str) -> bool:
        grants = self._read_grants()
        selected = next((g for g in grants if g.get("id") == approval_id and g.get("action") == action), None)
        if selected is None:
            return False
        kept = [g for g in grants if not (g.get("id") == approval_id and g.get("action") == action)]
        self._write_grants(kept)
        self.audit("approval_consumed", f"{approval_id}:{action}")
        return True

    def audit(self, action: str, target: str) -> None:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"action": action, "target": target, "mode": self.mode}, ensure_ascii=True)
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _contains_denied_marker(self, text: str) -> bool:
        return any(marker in text for marker in self._deny_markers)

    def _is_high_risk_command(self, text: str) -> bool:
        return any(token in text for token in self._high_risk_tokens)

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

    def _read_approvals(self) -> list[dict]:
        try:
            if APPROVALS_FILE.exists():
                data = json.loads(APPROVALS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning(f"Failed to read approvals: {e}")
        return []

    def _write_approvals(self, approvals: list[dict]) -> None:
        APPROVALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        APPROVALS_FILE.write_text(json.dumps(approvals, indent=2), encoding="utf-8")

    def _read_grants(self) -> list[dict]:
        try:
            if GRANTS_FILE.exists():
                data = json.loads(GRANTS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning(f"Failed to read approval grants: {e}")
        return []

    def _write_grants(self, grants: list[dict]) -> None:
        GRANTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        GRANTS_FILE.write_text(json.dumps(grants, indent=2), encoding="utf-8")


capability_guard = CapabilityGuard()
