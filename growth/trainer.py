"""
Runs nightly. Takes collected interactions rated as good (quality > 0.7),
formats them as fine-tuning data, runs QLoRA on the base personality model,
saves the adapter. Next boot uses the new adapter.
"""

import json
import runpy
import sys
from contextlib import contextmanager
from pathlib import Path

from loguru import logger

import config


ADAPTERS_DIR = config.DATA_DIR / "identity" / "lora_adapters"
TRAINING_DATA_DIR = config.DATA_DIR / "training"
ADAPTERS_DIR.mkdir(parents=True, exist_ok=True)
TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def _monkeypatch_gguf_enums():
    import gguf

    aliases = {
        "DEEPSEEK2OCR": gguf.MODEL_ARCH.DEEPSEEK2,
        "GEMMA4": gguf.MODEL_ARCH.GEMMA3,
        "MISTRAL4": gguf.MODEL_ARCH.MISTRAL3,
    }

    applied = {}
    for name, target in aliases.items():
        if not hasattr(gguf.MODEL_ARCH, name):
            setattr(gguf.MODEL_ARCH, name, target)
            applied[name] = target

    try:
        yield
    finally:
        for name in applied:
            try:
                delattr(gguf.MODEL_ARCH, name)
            except Exception:
                pass


def _run_hf_to_gguf_converter(source_dir: Path, output_file: Path) -> bool:
    import gguf

    script_path = Path(gguf.__file__).resolve().parent.parent / "bin" / "convert_hf_to_gguf.py"
    if not script_path.exists():
        logger.warning(f"[Training] Converter script not found: {script_path}")
        return False

    argv_backup = sys.argv[:]
    try:
        with _monkeypatch_gguf_enums():
            sys.argv = [
                str(script_path),
                str(source_dir),
                "--outfile",
                str(output_file),
                "--outtype",
                "f16",
            ]
            runpy.run_path(str(script_path), run_name="__main__")
        return output_file.exists()
    except SystemExit as e:
        return e.code == 0 and output_file.exists()
    except Exception as e:
        logger.warning(f"[Training] GGUF conversion failed: {e}")
        return False
    finally:
        sys.argv = argv_backup


def _merge_and_convert_adapter(adapter_dir: Path, hf_model_id: str) -> Path | None:
    merged_hf_dir = adapter_dir / "merged_hf"
    merged_gguf = adapter_dir / "merged_model.gguf"

    try:
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info("[Training] Loading base model for merge-and-convert")
        tokenizer = AutoTokenizer.from_pretrained(hf_model_id)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        base_model = AutoModelForCausalLM.from_pretrained(
            hf_model_id,
            torch_dtype="auto",
            device_map="auto",
            low_cpu_mem_usage=True,
        )

        peft_model = PeftModel.from_pretrained(base_model, str(adapter_dir), is_trainable=False)
        merged_model = peft_model.merge_and_unload()
        merged_hf_dir.mkdir(parents=True, exist_ok=True)
        merged_model.save_pretrained(merged_hf_dir, safe_serialization=True)
        tokenizer.save_pretrained(merged_hf_dir)

        if _run_hf_to_gguf_converter(merged_hf_dir, merged_gguf):
            logger.success(f"[Training] Merged GGUF exported to {merged_gguf}")
            return merged_gguf

        logger.warning("[Training] Merged HF model saved, but GGUF export did not complete")
        return None
    except Exception as e:
        logger.warning(f"[Training] Merge-and-convert failed: {e}")
        return None


async def run_nightly_finetune():
    """Called by the idle daemon at 3am"""
    logger.info("[Training] Starting nightly LoRA fine-tune")

    # Collect all good interactions
    good_examples = []
    for batch_file in TRAINING_DATA_DIR.glob("batch_*.json"):
        with open(batch_file, encoding="utf-8") as f:
            batch = json.load(f)
        good = [ex for ex in batch if ex.get("quality", 0) > 0.7]
        good_examples.extend(good)

    if len(good_examples) < 20:
        logger.info(f"[Training] Only {len(good_examples)} good examples, need 20+. Skipping.")
        return

    logger.info(f"[Training] Fine-tuning on {len(good_examples)} examples")

    # Format as conversation fine-tuning data
    formatted = []
    for ex in good_examples:
        formatted.append({
            "instruction": ex["user"],
            "output": ex["assistant"],
        })

    # Write to temp training file
    train_file = TRAINING_DATA_DIR / "current_train.json"
    with open(train_file, "w", encoding="utf-8") as f:
        json.dump(formatted, f)

    # Run QLoRA training (this is the real fine-tuning)
    try:
        from datasets import Dataset
        from datetime import datetime
        import torch
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
        from trl import SFTTrainer

        # For GGUF models, use the HuggingFace source model for training
        hf_model_id = "NousResearch/Hermes-3-Llama-3.1-8B"

        tokenizer = AutoTokenizer.from_pretrained(hf_model_id)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            hf_model_id,
            load_in_4bit=True,  # QLoRA — 4-bit quantization
            device_map="auto",
            torch_dtype=torch.float16,
        )

        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            target_modules=["q_proj", "v_proj"],
        )
        model = get_peft_model(model, lora_config)

        dataset = Dataset.from_list(
            [{"text": f"### User: {ex['instruction']}\n### AERIS: {ex['output']}"} for ex in formatted]
        )

        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset,
            dataset_text_field="text",
            args=TrainingArguments(
                output_dir=str(ADAPTERS_DIR / "latest"),
                num_train_epochs=2,
                per_device_train_batch_size=1,
                gradient_accumulation_steps=4,
                learning_rate=2e-4,
                fp16=True,
                logging_steps=10,
                save_strategy="epoch",
                report_to="none",
            ),
        )
        trainer.train()
        model.save_pretrained(str(ADAPTERS_DIR / "latest"))

        merged_gguf = _merge_and_convert_adapter(ADAPTERS_DIR / "latest", hf_model_id)

        marker = {
            "created": datetime.now().isoformat(),
            "format": "peft_safetensors",
            "runtime_compatible": merged_gguf is not None,
            "runtime_expected": "gguf_merged_model" if merged_gguf else "gguf_lora",
            "merged_model": str(merged_gguf) if merged_gguf else None,
            "notes": "If gguf export succeeds, the merged model is loaded at boot; otherwise the adapter remains as an artifact.",
        }
        with open(ADAPTERS_DIR / "latest" / "adapter_meta.json", "w", encoding="utf-8") as f:
            json.dump(marker, f, indent=2)

        logger.success(f"[Training] LoRA adapter saved to {ADAPTERS_DIR / 'latest'}")

    except Exception as e:
        logger.error(f"[Training] Fine-tune failed: {e}")
