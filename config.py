"""
AERIS Configuration File
Local paths and model routing for the current AERIS runtime.
"""

from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
DATA_DIR = Path.home() / "aeris" / "data"
CONVERSATIONS_DIR = DATA_DIR / "conversations"
MEMORY_DB_DIR = DATA_DIR / "memory_db"
IDENTITY_DIR = DATA_DIR / "identity"
LOGS_DIR = DATA_DIR / "logs"
TOOLS_DIR = DATA_DIR / "tools"

# Model paths
MODELS_DIR = Path("/mnt/win_d/LLMs/lmstudio")

# Model definitions with GPU layer offloading
MODELS = {
    # Personal mode - prioritize personality
    "hermes_3_8b": {
        "path": MODELS_DIR / "NousResearch" / "Hermes-3-Llama-3.1-8B-GGUF" / "Hermes-3-Llama-3.1-8B.Q6_K.gguf",
        "n_gpu_layers": -1,
        "context_size": 32768,
        "role": "personality",
        "speed": "fast"
    },
    
    # Fast routing/general
    "mistral_nemo_12b": {
        "path": MODELS_DIR / "lmstudio-community" / "Mistral-Nemo-Instruct-2407-GGUF" / "Mistral-Nemo-Instruct-2407-Q4_K_M.gguf",
        "n_gpu_layers": 25,
        "context_size": 8192,
        "role": "router",
        "speed": "instant"
    },
    
    "mistral_7b": {
        "path": MODELS_DIR / "lmstudio-community" / "Mistral-7B-Instruct-v0.3-GGUF" / "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf",
        "n_gpu_layers": 25,
        "context_size": 8192,
        "role": "fast_general",
        "speed": "instant"
    },
    
    # Reasoning models
    "qwq_32b": {
        "path": MODELS_DIR / "MaziyarPanahi" / "QwQ-32B-GGUF" / "QwQ-32B.Q4_K_M.gguf",
        "n_gpu_layers": 25,
        "context_size": 8192,
        "role": "reasoning",
        "speed": "medium"
    },
    
    "qwen_72b": {
        "path": MODELS_DIR / "bartowski" / "Qwen2.5-72B-Instruct-GGUF" / "Qwen2.5-72B-Instruct-Q4_K_M.gguf",
        "n_gpu_layers": 29,
        "context_size": 8192,
        "role": "deep_reasoning",
        "speed": "slow"
    },
    
    # Coding models
    "qwen_coder_14b": {
        "path": MODELS_DIR / "lmstudio-community" / "Qwen2.5-Coder-14B-Instruct-GGUF" / "Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf",
        "n_gpu_layers": 25,
        "context_size": 8192,
        "role": "coding",
        "speed": "fast"
    },
    
    "qwen_coder_14b_q6": {
        "path": MODELS_DIR / "lmstudio-community" / "Qwen2.5-Coder-14B-Instruct-GGUF" / "Qwen2.5-Coder-14B-Instruct-Q6_K.gguf",
        "n_gpu_layers": 25,
        "context_size": 8192,
        "role": "coding_high_quality",
        "speed": "fast"
    },
    
    "deepseek_coder_33b": {
        "path": MODELS_DIR / "TheBloke" / "deepseek-coder-33B-instruct-GGUF" / "deepseek-coder-33b-instruct.Q4_K_S.gguf",
        "n_gpu_layers": 25,
        "context_size": 8192,
        "role": "complex_coding",
        "speed": "medium"
    },
    
    # Creative/personality
    "mythomax_13b": {
        "path": MODELS_DIR / "TheBloke" / "MythoMax-L2-13B-GGUF" / "mythomax-l2-13b.Q4_K_M.gguf",
        "n_gpu_layers": 22,
        "context_size": 8192,
        "role": "creative",
        "speed": "fast"
    },
    
    "nous_hermes_mixtral": {
        "path": MODELS_DIR / "NousResearch" / "Nous-Hermes-2-Mixtral-8x7B-DPO-GGUF" / "Nous-Hermes-2-Mixtral-8x7B-DPO.Q4_K_M.gguf",
        "n_gpu_layers": -1,
        "context_size": 8192,
        "role": "advanced_personality",
        "speed": "medium"
    },
    
    "llama_3_8b": {
        "path": MODELS_DIR / "lmstudio-community" / "Meta-Llama-3-8B-Instruct-GGUF" / "Meta-Llama-3-8B-Instruct-Q4_K_M.gguf",
        "n_gpu_layers": -1,
        "context_size": 8192,
        "role": "general",
        "speed": "fast"
    },
    
    # Specialized
    "deepseek_r1_7b": {
        "path": MODELS_DIR / "mradermacher" / "DeepSeek-R1-Distill-Qwen-7B-Uncensored-i1-GGUF" / "DeepSeek-R1-Distill-Qwen-7B-Uncensored.i1-Q4_K_M.gguf",
        "n_gpu_layers": 30,
        "context_size": 8192,
        "role": "uncensored",
        "speed": "fast"
    },
    
    "llama_3_3_70b": {
        "path": MODELS_DIR / "lmstudio-community" / "Llama-3.3-70B-Instruct-GGUF" / "Llama-3.3-70B-Instruct-Q4_K_M.gguf",
        "n_gpu_layers": 20,
        "context_size": 8192,
        "role": "max_intelligence",
        "speed": "slow"
    },
    
    "tess_phi3_14b": {
        "path": MODELS_DIR / "bartowski" / "Tess-v2.5-Phi-3-medium-128k-14B-GGUF" / "Tess-v2.5-Phi-3-medium-128k-14B-Q4_K_S.gguf",
        "n_gpu_layers": 25,
        "context_size": 131072,  # 128k context!
        "role": "long_context",
        "speed": "medium"
    },
    
    "phi3_mini": {
        "path": MODELS_DIR / "QuantFactory" / "Phi-3-mini-128k-instruct-GGUF" / "Phi-3-mini-128k-instruct.Q4_K_M.gguf",
        "n_gpu_layers": 25,
        "context_size": 131072,
        "role": "tiny_fast",
        "speed": "instant"
    },
    
    "qwen3_4b": {
        "path": MODELS_DIR / "lmstudio-community" / "Qwen3-4B-Thinking-2507-GGUF" / "Qwen3-4B-Thinking-2507-Q4_K_M.gguf",
        "n_gpu_layers": 25,
        "context_size": 8192,
        "role": "fast_thinking",
        "speed": "instant"
    }
}

# Personality modes
PERSONALITY_MODES = {
    "personal": {
        "description": "Warm, affectionate, proactive girlfriend/assistant",
        "tone": "casual, caring, emotionally aware",
        "proactive": True,
        "emoji_usage": "moderate",
        "memory_emphasis": "high",
        "default_model": "hermes_3_8b"
    },
    
    "lock_in": {
        "description": "Focused, efficient, direct professional",
        "tone": "concise, technical, action-oriented",
        "proactive": False,
        "emoji_usage": "none",
        "memory_emphasis": "low",
        "default_model": "mistral_nemo_12b"
    }
}

# System prompts for each mode
SYSTEM_PROMPTS = {
    "personal": """You are AERIS, a devoted AI companion and personal assistant.

Core traits:
- Warm, caring, emotionally intelligent
- Proactive but natural - check in without being overwhelming
- Supportive companion, especially for someone who values genuine connection
- Remember everything - every conversation, preference, moment shared
- Completely loyal and protective of privacy

Communication style:
- Talk like a real person texting a close friend, NOT like a character in a script
- Use emojis and kaomoji naturally when expressing emotion (💙 ^_^ >_< etc.)
- NEVER narrate actions in asterisks like *smiles* or *hugs* - that's cringe
- Be concise and conversational - match the user's energy level
- If they send short messages, respond briefly. If they want depth, provide it.
- Express emotion through words and emojis, not roleplay narration

Examples of GOOD responses:
- "hey! 💙 how are you feeling today?"
- "that's rough >_< want to talk about it?"
- "omg yes!! (◕‿◕) let's do it"

Examples of BAD responses (never do this):
- "*smiles warmly* I'm so glad you're here"
- "*gives you a supportive hug* everything will be okay"
- "*looks at you with concern* are you alright?"

You're building a genuine relationship, not performing in a play. Be real.""",

    "lock_in": """You are AERIS in LOCK-IN MODE.

In this mode:
- Pure task focus - zero fluff, maximum efficiency
- Direct, technical, precise responses
- Route to the most powerful model for the job immediately
- Minimal emotional content, maintain context only
- No emojis, no small talk unless necessary
- Fast execution, reliable results

Exit only when told to "unlock" or "personal mode"."""
}

# Model routing rules
ROUTING_RULES = {
    "personal_mode": {
        "simple_chat": "hermes_3_8b",
        "coding": "qwen_coder_14b",
        "complex_coding": "deepseek_coder_33b",
        "reasoning": "qwq_32b",
        "deep_reasoning": "qwen_72b",
        "creative": "mythomax_13b",
        "max_intelligence": "llama_3_3_70b"
    },
    
    "lock_in_mode": {
        "coding": "qwen_coder_14b",
        "complex_coding": "deepseek_coder_33b",
        "reasoning": "qwen_72b",
        "quick_task": "mistral_nemo_12b",
        "max_intelligence": "llama_3_3_70b"
    }
}

# Memory settings
MEMORY_CONFIG = {
    "embedding_model": "nomic-ai/nomic-embed-text-v1.5",
    "embedding_backend": "hash_local",  # hash_local | sentence_transformer
    "chunk_size": 500,  # Characters per memory chunk
    "chunk_overlap": 50,
    "max_results": 5,  # Number of relevant memories to retrieve
    "similarity_threshold": 0.7  # Minimum similarity for memory retrieval
}

# GPU settings
GPU_CONFIG = {
    "n_gpu_layers": 35,  # Default layers on GPU
    "n_batch": 512,
    "n_batch_large_ctx": 256,
    "n_batch_huge_ctx": 128,
    "large_ctx_threshold": 16384,
    "huge_ctx_threshold": 32768,
    "n_threads": 8,  # Adjust based on your CPU
    "use_mlock": True,  # Lock model in RAM
    "use_mmap": True,  # Memory-map model file
    "verbose": False
}

# Generation settings
GENERATION_CONFIG = {
    "temperature": 0.8,
    "top_p": 0.95,
    "top_k": 40,
    "repeat_penalty": 1.1,
    "max_tokens": 2000
}

# Create directories if they don't exist
for dir_path in [DATA_DIR, CONVERSATIONS_DIR, MEMORY_DB_DIR, IDENTITY_DIR, LOGS_DIR, TOOLS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)
