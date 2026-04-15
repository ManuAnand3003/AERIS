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
                return Path(params["path"]).read_text(encoding="utf-8")
            
            elif name == "write_file":
                p = Path(params["path"])
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(params["content"], encoding="utf-8")
                return f"Written to {params['path']}"
            
            elif name == "run_shell":
                cmd = params["command"]
                # Safety: block destructive commands
                blocked = ["rm -rf", "mkfs", "dd if=", ":(){", "fork bomb"]
                if any(b in cmd for b in blocked):
                    return "[Blocked: potentially destructive command]"
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
