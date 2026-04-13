"""
AERIS Model Manager
Handles loading, switching, and managing multiple AI models with GPU acceleration
"""

from llama_cpp import Llama
from pathlib import Path
import time
import gc
import config

class ModelManager:
    def __init__(self):
        self.current_model = None
        self.current_model_name = None
        self.model_cache = {}
        self.load_stats = {}
        
    def load_model(self, model_name: str, verbose: bool = True):
        """Load a specific model with GPU acceleration"""
        
        if model_name not in config.MODELS:
            raise ValueError(f"Model '{model_name}' not found in config.MODELS")
        
        model_config = config.MODELS[model_name]
        model_path = model_config["path"]
        
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model file not found: {model_path}\n"
                f"Please check your models folder: {config.MODELS_DIR}"
            )
        
        if self.current_model_name == model_name:
            if verbose:
                print(f"[Model '{model_name}' already loaded]")
            return self.current_model
        
        if self.current_model is not None:
            if verbose:
                print(f"[Unloading {self.current_model_name}...]")
            self._unload_current_model()
        
        if verbose:
            print(f"\n[Loading {model_name}...]")
            print(f"  Path: {model_path.name}")
            print(f"  GPU Layers: {model_config['n_gpu_layers']}")
            print(f"  Role: {model_config['role']}")
        
        start_time = time.time()
        
        try:
            model = Llama(
                model_path=str(model_path),
                n_gpu_layers=model_config["n_gpu_layers"],
                n_ctx=model_config["context_size"],
                n_batch=config.GPU_CONFIG["n_batch"],
                n_threads=config.GPU_CONFIG["n_threads"],
                use_mlock=config.GPU_CONFIG["use_mlock"],
                use_mmap=config.GPU_CONFIG["use_mmap"],
                verbose=config.GPU_CONFIG["verbose"]
            )
            
            load_time = time.time() - start_time
            self.load_stats[model_name] = load_time
            
            self.current_model = model
            self.current_model_name = model_name
            
            if verbose:
                print(f"[✓ Loaded in {load_time:.2f}s]")
                print(f"[Speed tier: {model_config['speed']}]\n")
            
            return model
            
        except Exception as e:
            print(f"[✗ Error loading model: {e}]")
            raise
    
    def _unload_current_model(self):
        """Unload current model and free memory"""
        if self.current_model is not None:
            del self.current_model
            self.current_model = None
            self.current_model_name = None
            gc.collect()
    
    def generate(self, prompt: str, system_prompt: str = "", **kwargs):
        """Generate response from current model"""
        
        if self.current_model is None:
            raise RuntimeError("No model loaded. Call load_model() first.")
        
        gen_config = {**config.GENERATION_CONFIG, **kwargs}
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.current_model.create_chat_completion(
                messages=messages,
                temperature=gen_config["temperature"],
                top_p=gen_config["top_p"],
                top_k=gen_config["top_k"],
                repeat_penalty=gen_config["repeat_penalty"],
                max_tokens=gen_config["max_tokens"],
                stream=False
            )
            
            return response["choices"][0]["message"]["content"]
            
        except Exception as e:
            return f"[Error generating response: {e}]"
    
    def generate_stream(self, prompt: str, system_prompt: str = "", **kwargs):
        """Generate streaming response from current model"""
        
        if self.current_model is None:
            raise RuntimeError("No model loaded. Call load_model() first.")
        
        gen_config = {**config.GENERATION_CONFIG, **kwargs}
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            stream = self.current_model.create_chat_completion(
                messages=messages,
                temperature=gen_config["temperature"],
                top_p=gen_config["top_p"],
                top_k=gen_config["top_k"],
                repeat_penalty=gen_config["repeat_penalty"],
                max_tokens=gen_config["max_tokens"],
                stream=True
            )
            
            for chunk in stream:
                if "choices" in chunk and len(chunk["choices"]) > 0:
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta:
                        yield delta["content"]
                        
        except Exception as e:
            yield f"[Error in streaming: {e}]"
    
    def get_model_info(self, model_name: str = None):
        """Get information about a model"""
        if model_name is None:
            model_name = self.current_model_name
        
        if model_name is None:
            return "No model loaded"
        
        if model_name not in config.MODELS:
            return f"Model '{model_name}' not found"
        
        model_config = config.MODELS[model_name]
        info = {
            "name": model_name,
            "role": model_config["role"],
            "speed": model_config["speed"],
            "gpu_layers": model_config["n_gpu_layers"],
            "context_size": model_config["context_size"],
            "loaded": model_name == self.current_model_name
        }
        
        if model_name in self.load_stats:
            info["last_load_time"] = f"{self.load_stats[model_name]:.2f}s"
        
        return info
    
    def list_available_models(self):
        """List all available models"""
        models = []
        for name, config_data in config.MODELS.items():
            models.append({
                "name": name,
                "role": config_data["role"],
                "speed": config_data["speed"],
                "available": config_data["path"].exists()
            })
        return models
    
    def cleanup(self):
        """Clean up and unload all models"""
        self._unload_current_model()
        self.model_cache.clear()
        gc.collect()


# Singleton instance
_model_manager = None

def get_model_manager():
    """Get the global ModelManager instance"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
