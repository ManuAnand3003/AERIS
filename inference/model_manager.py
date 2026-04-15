import asyncio
import gc
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from llama_cpp import Llama
from loguru import logger

from system.monitor import monitor
import config


class ModelManager:
    def __init__(self):
        self.current_model: Llama | None = None
        self.current_model_name: str | None = None
        self.current_adapter_path: Path | None = None
        self.current_model_source_path: Path | None = None
        self.current_ctx: int | None = None
        self.current_n_batch: int | None = None
        self.active_adapter_path: Path | None = None
        self.active_merged_model_path: Path | None = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="llama")
        self._lock = asyncio.Lock()
        self.load_stats: dict = {}

    def refresh_finetune_artifacts(self) -> tuple[Path | None, Path | None]:
        """Discover the newest compatible LoRA artifact set for runtime loading."""
        latest_dir = config.DATA_DIR / "identity" / "lora_adapters" / "latest"
        latest_dir.mkdir(parents=True, exist_ok=True)

        merged_model = latest_dir / "merged_model.gguf"
        if not merged_model.exists():
            merged_model = None

        preferred = [latest_dir / "adapter.gguf", latest_dir / "lora.gguf"]
        gguf_files = sorted(latest_dir.glob("*.gguf"))

        selected: Path | None = None
        for candidate in preferred:
            if candidate.exists():
                selected = candidate
                break
        if selected is None and gguf_files:
            selected = gguf_files[-1]

        self.active_adapter_path = selected
        self.active_merged_model_path = merged_model

        if merged_model:
            logger.info(f"Merged fine-tuned model ready: {merged_model}")
        elif selected:
            logger.info(f"Adapter ready: {selected}")
        else:
            peft_adapter = latest_dir / "adapter_model.safetensors"
            if peft_adapter.exists():
                logger.warning(
                    "Found PEFT adapter weights, but llama.cpp needs a GGUF LoRA adapter for runtime loading."
                )

        return self.active_adapter_path, self.active_merged_model_path

    def refresh_adapter(self) -> Path | None:
        """Backward-compatible alias for adapter discovery."""
        adapter_path, _ = self.refresh_finetune_artifacts()
        return adapter_path

    def _finetune_for_model(self, model_name: str) -> tuple[Path | None, Path | None]:
        default_personal_model = config.PERSONALITY_MODES.get("personal", {}).get("default_model")
        if model_name != default_personal_model:
            return None, None
        return self.refresh_finetune_artifacts()

    async def load_model(self, model_name: str) -> bool:
        async with self._lock:
            desired_adapter, desired_merged = self._finetune_for_model(model_name)
            desired_source = desired_merged or desired_adapter

            if (
                self.current_model_name == model_name
                and self.current_adapter_path == desired_adapter
                and self.current_model_source_path == desired_source
            ):
                return True

            can_load, reason = monitor.can_load_model(model_name)
            if not can_load:
                logger.error(f"Cannot load {model_name}: {reason}")
                return False

            if self.current_model:
                await self._unload()

            model_cfg = config.MODELS.get(model_name)
            if not model_cfg:
                logger.error(f"Model '{model_name}' not in config")
                return False

            model_path = desired_merged or model_cfg["path"]
            if not model_path.exists():
                logger.error(f"Model file not found: {model_path}")
                return False

            logger.info(f"Loading {model_name} ({model_cfg['role']})...")
            start = time.time()

            loop = asyncio.get_running_loop()
            target_ctx = int(model_cfg["context_size"])
            fallback_ctx = [target_ctx]
            for candidate in (32768, 16384, 8192, 4096):
                if candidate < target_ctx and candidate not in fallback_ctx:
                    fallback_ctx.append(candidate)

            def _n_batch_for_ctx(ctx_size: int) -> int:
                if ctx_size >= config.GPU_CONFIG["huge_ctx_threshold"]:
                    return config.GPU_CONFIG["n_batch_huge_ctx"]
                if ctx_size >= config.GPU_CONFIG["large_ctx_threshold"]:
                    return config.GPU_CONFIG["n_batch_large_ctx"]
                return config.GPU_CONFIG["n_batch"]

            try:
                last_err: Exception | None = None
                loaded_with_adapter = False
                for ctx_size in fallback_ctx:
                    n_batch = _n_batch_for_ctx(ctx_size)
                    adapter_attempts = [desired_adapter, None] if desired_adapter and desired_merged is None else [None]

                    for adapter_path in adapter_attempts:
                        try:
                            adapter_note = f", adapter={adapter_path.name}" if adapter_path else ""
                            logger.info(f"Trying load config: n_ctx={ctx_size}, n_batch={n_batch}{adapter_note}")
                            self.current_model = await loop.run_in_executor(
                                self._executor,
                                lambda: Llama(
                                    model_path=str(model_path),
                                    n_gpu_layers=model_cfg["n_gpu_layers"],
                                    n_ctx=ctx_size,
                                    n_batch=n_batch,
                                    n_threads=config.GPU_CONFIG["n_threads"],
                                    use_mlock=config.GPU_CONFIG["use_mlock"],
                                    use_mmap=config.GPU_CONFIG["use_mmap"],
                                    lora_path=str(adapter_path) if adapter_path else None,
                                    verbose=False,
                                ),
                            )
                            self.current_ctx = ctx_size
                            self.current_n_batch = n_batch
                            self.current_adapter_path = adapter_path
                            self.current_model_source_path = model_path
                            loaded_with_adapter = adapter_path is not None
                            break
                        except Exception as e:
                            last_err = e
                            logger.warning(f"Load failed for n_ctx={ctx_size} adapter={adapter_path}: {e}")

                    if self.current_model is not None:
                        break

                if self.current_model is None:
                    raise RuntimeError(str(last_err) if last_err else "Unknown model load error")

                elapsed = time.time() - start
                self.current_model_name = model_name
                self.load_stats[model_name] = elapsed
                if loaded_with_adapter and self.current_adapter_path:
                    logger.success(
                        f"Loaded {model_name} + adapter {self.current_adapter_path.name} in {elapsed:.2f}s"
                    )
                elif desired_merged:
                    logger.success(f"Loaded {model_name} + merged fine-tune {model_path.name} in {elapsed:.2f}s")
                else:
                    logger.success(f"Loaded {model_name} in {elapsed:.2f}s")
                return True
            except Exception as e:
                logger.error(f"Failed to load {model_name}: {e}")
                return False

    async def generate(self, messages: list[dict], **kwargs) -> str:
        if not self.current_model:
            return "[No model loaded]"

        gen_cfg = {**config.GENERATION_CONFIG, **kwargs}
        loop = asyncio.get_running_loop()

        try:
            response = await loop.run_in_executor(
                self._executor,
                lambda: self.current_model.create_chat_completion(
                    messages=messages,
                    temperature=gen_cfg["temperature"],
                    top_p=gen_cfg["top_p"],
                    top_k=gen_cfg["top_k"],
                    repeat_penalty=gen_cfg["repeat_penalty"],
                    max_tokens=gen_cfg["max_tokens"],
                    stream=False,
                ),
            )
            return response["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Generation error: {e}")
            return f"[Generation error: {e}]"

    async def generate_stream(self, messages: list[dict], **kwargs):
        if not self.current_model:
            yield "[No model loaded]"
            return

        gen_cfg = {**config.GENERATION_CONFIG, **kwargs}
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _run():
            try:
                stream = self.current_model.create_chat_completion(
                    messages=messages,
                    temperature=gen_cfg["temperature"],
                    top_p=gen_cfg["top_p"],
                    max_tokens=gen_cfg["max_tokens"],
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk["choices"][0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        asyncio.run_coroutine_threadsafe(queue.put(token), loop)
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)
            except Exception as e:
                asyncio.run_coroutine_threadsafe(queue.put(f"[Error: {e}]"), loop)
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        self._executor.submit(_run)

        while True:
            token = await queue.get()
            if token is None:
                break
            yield token

    async def _unload(self):
        logger.info(f"Unloading {self.current_model_name}")
        del self.current_model
        self.current_model = None
        self.current_model_name = None
        self.current_adapter_path = None
        self.current_model_source_path = None
        self.current_ctx = None
        self.current_n_batch = None
        gc.collect()
        await asyncio.sleep(0.1)

    def health_snapshot(self) -> dict:
        return {
            "model": self.current_model_name or "none",
            "adapter": str(self.current_adapter_path) if self.current_adapter_path else "none",
            "source": str(self.current_model_source_path) if self.current_model_source_path else "none",
            "n_ctx": self.current_ctx,
            "n_batch": self.current_n_batch,
        }


model_manager = ModelManager()