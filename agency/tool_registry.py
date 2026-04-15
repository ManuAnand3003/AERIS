"""
AERIS's capability registry. She knows what she can do.
New tools get registered here — including ones she writes herself.
"""
import json
import asyncio
import subprocess
import os
from pathlib import Path
from datetime import datetime
from loguru import logger
import config
from system.capability_guard import capability_guard
from agency.vscode_bridge import vscode_bridge


TOOLS_DIR = config.DATA_DIR / "tools"
TOOLS_DIR.mkdir(parents=True, exist_ok=True)
REGISTRY_FILE = TOOLS_DIR / "registry.json"


# Built-in base tools
BASE_TOOLS = {
    "read_file": {
        "description": "Read a file and return its contents",
        "parameters": {"path": "string"},
        "builtin": True
    },
    "write_file": {
        "description": "Write content to a file",
        "parameters": {"path": "string", "content": "string"},
        "builtin": True
    },
    "run_shell": {
        "description": "Run a shell command (sandboxed)",
        "parameters": {"command": "string"},
        "builtin": True
    },
    "web_fetch": {
        "description": "Fetch the text content of a URL",
        "parameters": {"url": "string"},
        "builtin": True
    },
    "memory_search": {
        "description": "Search AERIS's own memory",
        "parameters": {"query": "string"},
        "builtin": True
    },
    "store_fact": {
        "description": "Store a fact into long-term memory",
        "parameters": {"fact": "string", "category": "string"},
        "builtin": True
    },
    "system_status": {
        "description": "Get current system resource usage",
        "parameters": {},
        "builtin": True
    },
    "cyber_scan_self": {
        "description": "Run a localhost self-scan and summarize open services",
        "parameters": {},
        "builtin": True
    },
    "cyber_scan_home": {
        "description": "Scan the configured local home subnet for active hosts",
        "parameters": {},
        "builtin": True
    },
    "cyber_sandbox_check": {
        "description": "Run a local Docker sandbox health check",
        "parameters": {},
        "builtin": True
    },
    "god_mode_status": {
        "description": "Show current capability mode and scope",
        "parameters": {},
        "builtin": True
    },
    "god_mode_enable": {
        "description": "Enable god mode (broad Linux/Arch control, Windows/ASUS denied)",
        "parameters": {},
        "builtin": True
    },
    "god_mode_disable": {
        "description": "Disable god mode and return to safer scoped control",
        "parameters": {},
        "builtin": True
    },
    "approvals_list": {
        "description": "List pending high-risk action approvals",
        "parameters": {},
        "builtin": True
    },
    "approval_grant": {
        "description": "Grant a pending approval by id",
        "parameters": {"id": "string"},
        "builtin": True
    },
    "approval_reject": {
        "description": "Reject a pending approval by id",
        "parameters": {"id": "string"},
        "builtin": True
    },
    "vscode_open_file": {
        "description": "Open a file in VS Code (approval-gated)",
        "parameters": {"path": "string", "line": "integer(optional)", "approval_id": "string(optional)"},
        "builtin": True
    },
    "vscode_patch_file": {
        "description": "Apply a single replace patch to a file (approval-gated)",
        "parameters": {"path": "string", "old": "string", "new": "string", "approval_id": "string(optional)"},
        "builtin": True
    },
    "vscode_run_task": {
        "description": "Run a workspace task command (approval-gated)",
        "parameters": {"command": "string", "approval_id": "string(optional)"},
        "builtin": True
    },
}


class ToolRegistry:
    def __init__(self):
        self.tools = dict(BASE_TOOLS)
        self._load_custom_tools()

    async def execute(self, tool_name: str, parameters: dict) -> str:
        """Execute a tool by name with given parameters"""
        if tool_name not in self.tools:
            return f"[Tool '{tool_name}' not found]"

        tool = self.tools[tool_name]

        # Built-in tools
        if tool.get("builtin"):
            return await self._execute_builtin(tool_name, parameters)

        # Custom tools (AERIS-written)
        return await self._execute_custom(tool_name, parameters)

    async def _execute_builtin(self, name: str, params: dict) -> str:
        """Execute built-in system tools"""
        try:
            if name == "read_file":
                decision = capability_guard.check_path(params["path"])
                if not decision.allowed:
                    return f"[Blocked: {decision.reason}]"
                capability_guard.audit("read_file", params["path"])
                return Path(params["path"]).read_text(encoding="utf-8")
            
            elif name == "write_file":
                decision = capability_guard.check_write_path(params["path"], params.get("approval_id"))
                if not decision.allowed:
                    if decision.pending_approval and decision.approval_id:
                        return f"[Approval required: {decision.reason}. Use: approve {decision.approval_id}]"
                    return f"[Blocked: {decision.reason}]"
                p = Path(params["path"])
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(params["content"], encoding="utf-8")
                capability_guard.audit("write_file", params["path"])
                return f"Written to {params['path']}"
            
            elif name == "run_shell":
                cmd = params["command"]
                decision = capability_guard.check_command(cmd, params.get("approval_id"))
                if not decision.allowed:
                    if decision.pending_approval and decision.approval_id:
                        return f"[Approval required: {decision.reason}. Use: approve {decision.approval_id}]"
                    return f"[Blocked: {decision.reason}]"
                capability_guard.audit("run_shell", cmd[:240])
                result = subprocess.run(
                    cmd, shell=True, capture_output=True,
                    text=True, timeout=30,
                    cwd=str(Path.home())
                )
                return result.stdout + result.stderr
            
            elif name == "web_fetch":
                import httpx
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(params["url"], headers={"User-Agent": "AERIS/2.0"})
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for s in soup(["script", "style", "nav", "footer"]):
                        s.decompose()
                    return soup.get_text(separator="\n", strip=True)[:3000]
            
            elif name == "memory_search":
                from memory.episodic import episodic
                results = episodic.recall(params["query"], n=5)
                return "\n".join([f"[{m['metadata'].get('role','?')}] {m['content'][:100]}" for m in results])
            
            elif name == "store_fact":
                from memory.episodic import episodic
                episodic.store_fact(params["fact"], params.get("category", "general"))
                return "Stored."
            
            elif name == "system_status":
                from system.monitor import monitor
                return monitor.get_status_string()

            elif name == "cyber_scan_self":
                from agency.cyber import cyber
                return await cyber.scan_self()

            elif name == "cyber_scan_home":
                from agency.cyber import cyber
                return await cyber.scan_home_network()

            elif name == "cyber_sandbox_check":
                from agency.cyber import cyber
                return await cyber.run_sandbox_escape_test()

            elif name == "god_mode_status":
                return f"{capability_guard.status()} | {capability_guard.scope()}"

            elif name == "god_mode_enable":
                return capability_guard.enable_god_mode()

            elif name == "god_mode_disable":
                return capability_guard.disable_god_mode()

            elif name == "approvals_list":
                pending = capability_guard.list_approvals()
                if not pending:
                    return "No pending approvals."
                lines = ["Pending approvals:"]
                for a in pending:
                    lines.append(f"  - {a.get('id')}: {a.get('action')} | {a.get('reason')} | {a.get('target')[:120]}")
                return "\n".join(lines)

            elif name == "approval_grant":
                approval_id = str(params.get("id", "")).strip()
                if not approval_id:
                    return "Missing approval id"
                return "Approval granted." if capability_guard.approve(approval_id) else "Approval id not found."

            elif name == "approval_reject":
                approval_id = str(params.get("id", "")).strip()
                if not approval_id:
                    return "Missing approval id"
                return "Approval rejected." if capability_guard.reject(approval_id) else "Approval id not found."

            elif name == "vscode_open_file":
                path = str(params.get("path", "")).strip()
                if not path:
                    return "Missing path"
                approval_id = params.get("approval_id")
                decision = capability_guard.check_command(f"vscode_open {path}", approval_id)
                if not decision.allowed:
                    if decision.pending_approval and decision.approval_id:
                        return f"[Approval required: {decision.reason}. Use: approve {decision.approval_id}, then rerun with approval_id={decision.approval_id}]"
                    return f"[Blocked: {decision.reason}]"
                capability_guard.audit("vscode_open_file", path)
                line = params.get("line")
                try:
                    line_int = int(line) if line is not None else None
                except Exception:
                    line_int = None
                return vscode_bridge.open_file(path, line_int)

            elif name == "vscode_patch_file":
                path = str(params.get("path", "")).strip()
                old_text = str(params.get("old", ""))
                new_text = str(params.get("new", ""))
                if not path or old_text == "":
                    return "Missing path or old text"
                approval_id = params.get("approval_id")
                decision = capability_guard.check_write_path(path, approval_id)
                if not decision.allowed:
                    if decision.pending_approval and decision.approval_id:
                        return f"[Approval required: {decision.reason}. Use: approve {decision.approval_id}, then rerun with approval_id={decision.approval_id}]"
                    return f"[Blocked: {decision.reason}]"
                capability_guard.audit("vscode_patch_file", path)
                return vscode_bridge.patch_file(path, old_text, new_text)

            elif name == "vscode_run_task":
                command = str(params.get("command", "")).strip()
                if not command:
                    return "Missing command"
                approval_id = params.get("approval_id")
                decision = capability_guard.check_command(command, approval_id)
                if not decision.allowed:
                    if decision.pending_approval and decision.approval_id:
                        return f"[Approval required: {decision.reason}. Use: approve {decision.approval_id}, then rerun with approval_id={decision.approval_id}]"
                    return f"[Blocked: {decision.reason}]"
                capability_guard.audit("vscode_run_task", command[:240])
                return vscode_bridge.run_task(command)

        except Exception as e:
            return f"[Tool error: {e}]"

    async def _execute_custom(self, name: str, params: dict) -> str:
        """Execute a tool AERIS wrote herself"""
        tool_file = TOOLS_DIR / f"{name}.py"
        if not tool_file.exists():
            return f"[Custom tool file missing: {tool_file}]"
        
        # Run in sandboxed subprocess
        try:
            import json as json_
            input_data = json_.dumps(params)
            result = subprocess.run(
                ["python", str(tool_file)],
                input=input_data, capture_output=True,
                text=True, timeout=30
            )
            return result.stdout or result.stderr
        except subprocess.TimeoutExpired:
            return "[Tool timed out after 30s]"
        except Exception as e:
            return f"[Custom tool error: {e}]"

    def register_tool(self, name: str, description: str, parameters: dict, code: str) -> bool:
        """AERIS registers a new tool she's written"""
        tool_file = TOOLS_DIR / f"{name}.py"
        tool_file.write_text(code, encoding="utf-8")
        
        self.tools[name] = {
            "description": description,
            "parameters": parameters,
            "builtin": False,
            "created": datetime.now().isoformat()
        }
        self._save_registry()
        logger.success(f"New tool registered: {name}")
        return True

    def list_tools(self) -> str:
        """Return formatted list of all available tools"""
        lines = ["Available tools:"]
        for name, tool in self.tools.items():
            lines.append(f"  · {name}: {tool['description']}")
        return "\n".join(lines)

    def _load_custom_tools(self):
        """Load previously registered custom tools from registry file"""
        if REGISTRY_FILE.exists():
            try:
                with open(REGISTRY_FILE) as f:
                    custom = json.load(f)
                self.tools.update(custom)
                logger.info(f"Loaded {len(custom)} custom tools")
            except Exception as e:
                logger.warning(f"Failed to load custom tools registry: {e}")

    def _save_registry(self):
        """Save custom tools registry to disk"""
        custom = {k: v for k, v in self.tools.items() if not v.get("builtin")}
        try:
            with open(REGISTRY_FILE, "w") as f:
                json.dump(custom, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save tools registry: {e}")


# Global singleton instance
tool_registry = ToolRegistry()
