"""Runtime feature orchestration for AERIS side services.

This keeps non-core features online when possible and sheds them when
system pressure is high.
"""

from __future__ import annotations

import asyncio
import os
import socket
import shutil
import subprocess
import sys
import time
from pathlib import Path

from loguru import logger

import config
from system.monitor import monitor


class FeatureController:
    def __init__(self) -> None:
        self.web_process: asyncio.subprocess.Process | None = None
        self.autopilot_enabled = True
        self.policy_profile = "full_online"
        self._last_action_ts = 0.0
        self._widget_window = "aeris-widget-bl"
        self._eww_config_dir = str(Path.home() / ".config" / "eww" / "aeris")
        self._widget_state_file = Path.home() / ".cache" / "aeris_widget_pos"
        self._widget_hidden_file = Path.home() / ".cache" / "aeris_widget_hidden"
        self._desktop_available = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))

        self._profiles = {
            "balanced": {
                "vram_pause": 0.90,
                "ram_pause": 0.88,
                "keep_widget_personal": True,
                "pause_web_on_pressure": True,
            },
            "full_online": {
                "vram_pause": 0.98,
                "ram_pause": 0.97,
                "keep_widget_personal": True,
                "pause_web_on_pressure": False,
            },
            "eco": {
                "vram_pause": 0.82,
                "ram_pause": 0.80,
                "keep_widget_personal": False,
                "pause_web_on_pressure": True,
            },
        }

    async def startup(self) -> None:
        await self.ensure_web_online()
        self.ensure_widget_online()

    async def shutdown(self) -> None:
        await self.stop_web()
        self.close_widget()

    async def ensure_web_online(self) -> str:
        if self.is_web_running():
            return "web already online"
        if self._is_web_port_open():
            return "web already online (external process)"

        env = os.environ.copy()
        env["PYTHONPATH"] = str(config.BASE_DIR)
        self.web_process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "uvicorn",
            "interface.web:app",
            "--host",
            "127.0.0.1",
            "--port",
            "7860",
            cwd=str(config.BASE_DIR),
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        logger.info("Web UI started on http://127.0.0.1:7860")
        return "web started"

    async def stop_web(self) -> str:
        if not self.web_process:
            return "web already offline"

        if self.web_process.returncode is None:
            self.web_process.terminate()
            try:
                await asyncio.wait_for(self.web_process.wait(), timeout=3)
            except asyncio.TimeoutError:
                self.web_process.kill()
                await self.web_process.wait()

        self.web_process = None
        logger.info("Web UI stopped")
        return "web stopped"

    def ensure_widget_online(self) -> str:
        if not self._desktop_available:
            return "desktop session unavailable"
        if shutil.which("eww") is None:
            return "eww not installed"
        if self._is_widget_hidden():
            return "widget hidden by user"

        target = self._preferred_widget_window()

        try:
            subprocess.run(["eww", "-c", self._eww_config_dir, "daemon"], check=False)
            subprocess.run(["eww", "-c", self._eww_config_dir, "open", target], check=False)
            return "widget started"
        except Exception as exc:
            logger.warning(f"Could not start widget: {exc}")
            return f"widget error: {exc}"

    def close_widget(self) -> str:
        if shutil.which("eww") is None:
            return "eww not installed"
        for window in ["aeris-widget-bl", "aeris-widget-br", "aeris-widget-tr", "aeris-widget-tl"]:
            subprocess.run(["eww", "-c", self._eww_config_dir, "close", window], check=False)
        return "widget closed"

    async def autopilot_tick(self, mode: str) -> str | None:
        if not self.autopilot_enabled:
            return None

        now = time.time()
        if now - self._last_action_ts < 45:
            return None

        cfg = self._profiles.get(self.policy_profile, self._profiles["balanced"])
        vram = monitor.get_vram_usage().get("fraction", 0)
        ram = monitor.get_ram_usage().get("fraction", 0)

        if vram >= cfg["vram_pause"] or ram >= cfg["ram_pause"]:
            if cfg["pause_web_on_pressure"] and self.is_web_running():
                await self.stop_web()
                self._last_action_ts = now
                return "autopilot: web paused due to high memory pressure"
            if mode == "lock_in":
                closed = self.close_widget()
                self._last_action_ts = now
                return f"autopilot: {closed} due to pressure in lock-in mode"
            return None

        if not self.is_web_running():
            await self.ensure_web_online()
            self._last_action_ts = now
            return "autopilot: web resumed"

        if mode == "personal" and cfg["keep_widget_personal"]:
            widget_status = self.ensure_widget_online()
            if widget_status in {"widget started"}:
                self._last_action_ts = now
                return "autopilot: widget resumed"

        return None

    def set_autopilot(self, enabled: bool) -> str:
        self.autopilot_enabled = enabled
        return f"autopilot {'enabled' if enabled else 'disabled'}"

    def set_policy_profile(self, profile: str) -> str:
        normalized = profile.strip().lower().replace(" ", "_")
        aliases = {
            "full": "full_online",
            "online": "full_online",
            "full-online": "full_online",
            "aggressive_save": "eco",
            "aggressive": "eco",
            "save": "eco",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized not in self._profiles:
            return "unknown profile. use: balanced | full_online | eco"
        self.policy_profile = normalized
        return f"policy set to {self.policy_profile}"

    def policy_status(self) -> str:
        cfg = self._profiles.get(self.policy_profile, self._profiles["balanced"])
        return (
            f"policy: {self.policy_profile} "
            f"(pause_vram>={cfg['vram_pause']:.2f}, pause_ram>={cfg['ram_pause']:.2f}, "
            f"keep_widget_personal={cfg['keep_widget_personal']}, pause_web_on_pressure={cfg['pause_web_on_pressure']})"
        )

    def is_web_running(self) -> bool:
        return bool(self.web_process and self.web_process.returncode is None)

    def _is_web_port_open(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            return sock.connect_ex(("127.0.0.1", 7860)) == 0

    def status_string(self) -> str:
        web = "online" if (self.is_web_running() or self._is_web_port_open()) else "offline"
        autopilot = "on" if self.autopilot_enabled else "off"
        widget = "ready" if shutil.which("eww") else "unavailable"
        hidden = "hidden" if self._is_widget_hidden() else "visible"
        return f"Features | web: {web} | widget: {widget}/{hidden} | autopilot: {autopilot} | policy: {self.policy_profile}"

    def _preferred_widget_window(self) -> str:
        try:
            if self._widget_state_file.exists():
                value = self._widget_state_file.read_text(encoding="utf-8").strip()
                if value in {"aeris-widget-bl", "aeris-widget-br", "aeris-widget-tr", "aeris-widget-tl"}:
                    return value
        except Exception:
            pass
        return self._widget_window

    def _is_widget_hidden(self) -> bool:
        return self._widget_hidden_file.exists()


feature_controller = FeatureController()