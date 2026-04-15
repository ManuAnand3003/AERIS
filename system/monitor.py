"""
Watches VRAM and RAM. AERIS never loads a model that will crash her.
This is the crash prevention that v1.0 never had.
"""

import subprocess

import psutil
from loguru import logger


class ResourceMonitor:
    VRAM_SAFE_THRESHOLD = 0.85
    RAM_SAFE_THRESHOLD = 0.80

    MODEL_VRAM_ESTIMATES = {
        "hermes_3_8b": 5.5,
        "qwen_coder_14b": 8.5,
        "mistral_nemo_12b": 7.0,
        "mythomax_13b": 7.5,
        "phi3_mini": 2.5,
        "qwen3_4b": 3.0,
        "deepseek_r1_7b": 4.5,
    }

    BLOCKED_MODELS = {"qwen_72b", "llama_3_3_70b", "qwq_32b", "deepseek_coder_33b", "nous_hermes_mixtral"}

    def get_vram_usage(self) -> dict:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
            )
            used, total = map(int, result.stdout.strip().split(", "))
            return {"used_gb": used / 1024, "total_gb": total / 1024, "fraction": used / total}
        except Exception as e:
            logger.warning(f"VRAM check failed: {e}")
            return {"used_gb": 0, "total_gb": 12, "fraction": 0}

    def get_ram_usage(self) -> dict:
        mem = psutil.virtual_memory()
        return {"used_gb": mem.used / 1e9, "total_gb": mem.total / 1e9, "fraction": mem.percent / 100}

    def can_load_model(self, model_name: str) -> tuple[bool, str]:
        if model_name in self.BLOCKED_MODELS:
            return False, f"Model '{model_name}' is permanently blocked (crashes on 32GB RAM)"

        vram = self.get_vram_usage()
        ram = self.get_ram_usage()

        estimated_vram = self.MODEL_VRAM_ESTIMATES.get(model_name, 8.0)
        vram_after = (vram["used_gb"] + estimated_vram) / vram["total_gb"]

        if vram_after > self.VRAM_SAFE_THRESHOLD:
            return False, f"Insufficient VRAM: need ~{estimated_vram}GB, only {vram['total_gb'] - vram['used_gb']:.1f}GB free"

        if ram["fraction"] > self.RAM_SAFE_THRESHOLD:
            return False, f"RAM too high: {ram['fraction'] * 100:.0f}% used"

        return True, "OK"

    def get_status_string(self) -> str:
        v = self.get_vram_usage()
        r = self.get_ram_usage()
        return f"VRAM: {v['used_gb']:.1f}/{v['total_gb']:.1f}GB | RAM: {r['used_gb']:.1f}/{r['total_gb']:.1f}GB"


monitor = ResourceMonitor()