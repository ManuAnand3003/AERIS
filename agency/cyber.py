"""
AERIS's cyber capabilities.
Runs on her own network. Tests her own systems.
Sandboxed — she doesn't go external without explicit permission.
"""

import asyncio
import os
import shutil
import subprocess

import nmap
from loguru import logger

from memory.episodic import episodic


class CyberAgent:
    def __init__(self):
        self.scanner = nmap.PortScanner()
        self.sandbox_active = False

    def _home_subnet(self) -> str:
        return os.getenv("AERIS_HOME_SUBNET", "192.168.1.0/24")

    async def scan_home_network(self) -> str:
        """Map devices on the local network."""
        logger.info("[Cyber] Scanning home network")
        try:
            loop = asyncio.get_running_loop()
            subnet = self._home_subnet()
            await loop.run_in_executor(
                None,
                lambda: self.scanner.scan(subnet, arguments="-sn"),
            )

            devices: list[str] = []
            for host in self.scanner.all_hosts():
                state = self.scanner[host].state()
                hostnames = self.scanner[host].hostnames()
                name = hostnames[0]["name"] if hostnames else ""
                label = f"{host} ({state})"
                if name:
                    label += f" {name}"
                devices.append(label)

            summary = f"Network scan on {subnet}: {len(devices)} devices found: {', '.join(devices) if devices else 'none'}"
            episodic.store_fact(summary, category="network_knowledge", importance=5)
            return summary
        except Exception as e:
            return f"Scan failed: {e}"

    async def scan_self(self) -> str:
        """Check her own open ports and services."""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: self.scanner.scan("127.0.0.1", arguments="-sV --open"),
            )

            ports: list[str] = []
            if "127.0.0.1" in self.scanner.all_hosts():
                localhost = self.scanner["127.0.0.1"]
                for proto in localhost.all_protocols():
                    for port in localhost[proto].keys():
                        service = localhost[proto][port]
                        ports.append(f"{port}/{proto} {service.get('name', '?')}")

            return f"Self-scan: open ports: {ports if ports else 'none'}"
        except Exception as e:
            return f"Self-scan failed: {e}"

    async def run_sandbox_escape_test(self) -> str:
        """
        Run a local sandbox health check.

        This intentionally avoids exploit attempts or escape tooling.
        It only verifies that Docker can start a disposable container.
        """
        logger.info("[Cyber] Starting sandbox health check")
        docker = shutil.which("docker")
        if docker is None:
            return "Docker unavailable. Install Docker if you want local sandbox checks."

        try:
            result = subprocess.run(
                ["docker", "run", "--rm", "alpine:3.20", "echo", "sandbox_up"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if "sandbox_up" in result.stdout:
                episodic.store_fact(
                    "Sandbox health check passed with disposable local container.",
                    category="security_sandbox",
                    importance=4,
                )
                return "Sandbox running. Escape testing module not implemented; local container health check passed."
            return f"Docker sandbox check failed: {result.stderr.strip() or result.stdout.strip()}"
        except subprocess.TimeoutExpired:
            return "Docker sandbox check timed out."
        except Exception as e:
            return f"Sandbox check failed: {e}"


cyber = CyberAgent()
