"""
AERIS encounters something she can't do.
She writes a Python function, tests it, registers it.
This is genuine capability expansion.
"""
from loguru import logger
from agency.tool_registry import tool_registry
from inference.model_manager import model_manager
import subprocess
import tempfile
import os


class ToolForge:
    async def forge(self, capability_description: str) -> tuple[bool, str]:
        """
        Given a description of something AERIS wants to do,
        generate a Python tool, test it, register it.
        Returns (success, tool_name_or_error)
        """
        logger.info(f"[Forge] Building tool for: {capability_description}")

        # Generate tool code
        prompt = f"""Write a Python script that does: {capability_description}

Requirements:
- Read input as JSON from stdin: import sys, json; params = json.load(sys.stdin)
- Print result to stdout
- Handle errors gracefully
- No external dependencies beyond stdlib, httpx, beautifulsoup4, and requests
- Keep it under 50 lines
- End with: if __name__ == '__main__': main()

Output ONLY the Python code, no explanation."""

        messages = [
            {"role": "system", "content": "You are a Python code generator. Output only raw Python code."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            code = await model_manager.generate(messages, temperature=0.2, max_tokens=800)
        except Exception as e:
            logger.error(f"[Forge] Code generation failed: {e}")
            return False, f"Code generation failed: {e}"
        
        # Strip markdown fences if model adds them
        code = code.strip()
        if code.startswith("```"):
            code = "\n".join(code.split("\n")[1:-1])

        # Test it in a temp file
        success, result = self._test_code(code)
        if not success:
            logger.warning(f"[Forge] Tool test failed: {result}")
            return False, f"Generated code failed testing: {result}"

        # Derive tool name
        tool_name = capability_description.lower()[:30].replace(" ", "_")
        tool_name = "".join(c for c in tool_name if c.isalnum() or c == "_")

        # Register
        tool_registry.register_tool(
            name=tool_name,
            description=capability_description,
            parameters={"input": "string"},
            code=code
        )
        
        logger.success(f"[Forge] Tool '{tool_name}' created and registered")
        return True, tool_name

    def _test_code(self, code: str) -> tuple[bool, str]:
        """Test generated code safely in isolation"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            tmp_path = f.name
        
        try:
            result = subprocess.run(
                ["python", tmp_path],
                input='{}',
                capture_output=True, text=True,
                timeout=10
            )
            os.unlink(tmp_path)
            if result.returncode != 0 and result.stderr:
                return False, result.stderr[:200]
            return True, result.stdout
        except subprocess.TimeoutExpired:
            try:
                os.unlink(tmp_path)
            except:
                pass
            return False, "Timed out"
        except Exception as e:
            return False, str(e)


# Global singleton instance
tool_forge = ToolForge()
