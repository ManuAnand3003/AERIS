import os
import sys
from pathlib import Path

from llama_cpp import Llama


def resolve_model_path() -> Path:
    candidates = []

    env_model = os.getenv("AERIS_MODEL_PATH")
    if env_model:
        candidates.append(Path(env_model).expanduser())

    candidates.append(Path(r"/mnt/windows-d/LLMs/lmstudio/NousResearch/Hermes-3-Llama-3.1-8B-GGUF/Hermes-3-Llama-3.1-8B.Q4_K_M.gguf"))
    candidates.append(Path(r"/mnt/win_d/LLMs/lmstudio/NousResearch/Hermes-3-Llama-3.1-8B-GGUF/Hermes-3-Llama-3.1-8B.Q4_K_M.gguf"))
    candidates.append(Path(r"D:\prompt-lab\models\NousResearch\Hermes-3-Llama-3.1-8B-GGUF\Hermes-3-Llama-3.1-8B.Q4_K_M.gguf"))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    searched = "\n".join(f"- {candidate}" for candidate in candidates)
    raise FileNotFoundError(
        "No test model found. Set AERIS_MODEL_PATH to a valid .gguf file.\n"
        f"Checked:\n{searched}"
    )


def main() -> int:
    model_path = resolve_model_path()
    print(f"Using model: {model_path}")

    model = Llama(
        model_path=str(model_path),
        n_gpu_layers=-1,
        n_ctx=2048,
        verbose=True,
    )

    response = model.create_chat_completion(
        messages=[{"role": "user", "content": "say hello in one sentence"}]
    )
    print(response["choices"][0]["message"]["content"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())