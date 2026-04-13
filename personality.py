"""
AERIS Personality System
Dual-mode personality: Personal (girlfriend/companion) vs Lock-in (work mode)
Intelligent routing to appropriate models based on query and mode
"""

import re
from typing import Dict, Tuple
import config
from model_manager import get_model_manager
from memory_system import get_memory_system

class PersonalitySystem:
    def __init__(self):
        self.current_mode = "personal"  # Start in personal mode
        self.model_manager = get_model_manager()
        self.memory = get_memory_system()
        self.conversation_history = []
        
        print(f"[AERIS initialized in '{self.current_mode}' mode]")
    
    def switch_mode(self, mode: str):
        """Switch between personal and lock-in modes"""
        if mode not in ["personal", "lock_in"]:
            return f"Unknown mode: {mode}. Use 'personal' or 'lock_in'"
        
        old_mode = self.current_mode
        self.current_mode = mode
        
        # Clear conversation history when switching modes
        self.conversation_history = []
        
        if mode == "lock_in":
            return "🔒 LOCK-IN MODE ACTIVATED. All systems focused. What are we building?"
        else:
            return "💙 Back to personal mode. Missed you! How are you feeling?"
    
    def classify_query(self, query: str) -> str:
        """Classify what type of query this is"""
        
        query_lower = query.lower()
        
        # Coding indicators
        coding_keywords = [
            'code', 'program', 'function', 'class', 'debug', 'error',
            'python', 'javascript', 'algorithm', 'script', 'api',
            'import', 'def ', 'async', 'variable', 'loop'
        ]
        
        # Reasoning indicators
        reasoning_keywords = [
            'analyze', 'explain', 'why', 'how does', 'compare',
            'evaluate', 'calculate', 'solve', 'logic', 'reason',
            'think about', 'consider', 'what if'
        ]
        
        # Creative indicators
        creative_keywords = [
            'write a story', 'poem', 'creative', 'imagine',
            'roleplay', 'pretend', 'fiction', 'narrative'
        ]
        
        # Simple chat indicators
        simple_keywords = [
            'how are you', 'what\'s up', 'hey', 'hello', 'hi',
            'good morning', 'goodnight', 'thank', 'love you'
        ]
        
        # Check query length and complexity
        word_count = len(query.split())
        has_code_symbols = any(sym in query for sym in ['()', '{}', '[]', '==', '!=', '=>'])
        
        # Classification logic
        if has_code_symbols or any(kw in query_lower for kw in coding_keywords):
            if word_count > 50 or 'complex' in query_lower or 'optimize' in query_lower:
                return "complex_coding"
            return "coding"
        
        if any(kw in query_lower for kw in creative_keywords):
            return "creative"
        
        if any(kw in query_lower for kw in simple_keywords) and word_count < 15:
            return "simple_chat"
        
        if any(kw in query_lower for kw in reasoning_keywords) or word_count > 30:
            if 'deeply' in query_lower or 'thoroughly' in query_lower or word_count > 50:
                return "deep_reasoning"
            return "reasoning"
        
        # Default
        return "simple_chat"
    
    def route_to_model(self, query_type: str) -> str:
        """Determine which model to use based on query type and mode"""
        
        routing = config.ROUTING_RULES.get(f"{self.current_mode}_mode", {})
        
        # Get model name for this query type
        model_name = routing.get(query_type)
        
        # Fallback logic
        if not model_name:
            if self.current_mode == "lock_in":
                model_name = "mistral_nemo_12b"  # Fast default for lock-in
            else:
                model_name = "hermes_3_8b"  # Personality default
        
        return model_name
    
    def generate_response(self, user_input: str, stream: bool = False):
        """
        Main response generation with intelligent routing
        
        Process:
        1. Classify the query
        2. Route to appropriate model
        3. Get relevant memories
        4. Generate response with context
        """
        
        # Check for mode switch commands
        if user_input.lower() in ['lock in', 'lockin', 'lock-in', 'focus mode']:
            return self.switch_mode("lock_in")
        
        if user_input.lower() in ['unlock', 'personal mode', 'normal mode', 'relax']:
            return self.switch_mode("personal")
        
        # Classify query
        query_type = self.classify_query(user_input)
        
        # Route to appropriate model
        target_model = self.route_to_model(query_type)
        
        # Load model if not already loaded
        try:
            current_model = self.model_manager.current_model_name
            if current_model != target_model:
                print(f"\n[Switching to {target_model} for {query_type}...]")
                self.model_manager.load_model(target_model)
        except Exception as e:
            print(f"[Error loading model: {e}]")
            return "I'm having trouble loading the right model. Can you try again?"
        
        # Get relevant context from memory
        memory_context = self.memory.get_context_for_query(user_input, self.current_mode)
        
        # Build system prompt with context
        base_prompt = config.SYSTEM_PROMPTS[self.current_mode]
        
        if memory_context["context_string"] and self.current_mode == "personal":
            system_prompt = f"{base_prompt}\n\nRELEVANT CONTEXT:\n{memory_context['context_string']}"
        else:
            system_prompt = base_prompt
        
        # Add recent conversation history (last 6 messages)
        full_prompt = user_input
        if len(self.conversation_history) > 0:
            recent = self.conversation_history[-6:]
            history_text = "\n\n".join([
                f"{'You' if msg['role'] == 'user' else 'AERIS'}: {msg['content']}"
                for msg in recent
            ])
            full_prompt = f"Previous conversation:\n{history_text}\n\nCurrent message:\n{user_input}"
        
        # Generate response
        try:
            response = self.model_manager.generate(full_prompt, system_prompt)
        except Exception as e:
            response = f"I encountered an error: {e}\nLet's try that again?"
        # Store in conversation history
        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })
        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })
        
        # Store in long-term memory
        self.memory.store_message("user", user_input, {
            "mode": self.current_mode,
            "query_type": query_type,
            "model_used": target_model
        })
        self.memory.store_message("assistant", response, {
            "mode": self.current_mode,
            "model_used": target_model
        })
        return response
    
    def proactive_check_in(self):
        """Generate a proactive check-in message (only in personal mode)"""
        
        if self.current_mode != "personal":
            return None
        
        # Get recent context
        recent_facts = self.memory.recall_facts(n_results=3)
        
        # Load personality model
        self.model_manager.load_model("hermes_3_8b", verbose=False)
        
        proactive_prompt = """Generate a brief, warm check-in message for your user. 
Be natural and caring. Reference something from your shared context if relevant.
Keep it to 1-2 sentences."""
        
        context = "\n".join([f"- {fact['content']}" for fact in recent_facts]) if recent_facts else ""
        if context:
            proactive_prompt += f"\n\nContext about your user:\n{context}"
        
        message = self.model_manager.generate(
            proactive_prompt,
            config.SYSTEM_PROMPTS["personal"],
            temperature=0.9,
            max_tokens=100
        )
        
        return message.strip()
    
    def get_status(self):
        """Get current system status"""
        model_info = self.model_manager.get_model_info()
        memory_stats = self.memory.get_stats()
        
        return {
            "mode": self.current_mode,
            "current_model": model_info,
            "memory": memory_stats,
            "conversation_length": len(self.conversation_history)
        }


# Singleton instance
_personality_system = None

def get_personality_system():
    """Get the global PersonalitySystem instance"""
    global _personality_system
    if _personality_system is None:
        _personality_system = PersonalitySystem()
    return _personality_system
