import re

from loguru import logger

from personality.identity import identity
from inference.model_manager import model_manager
from memory.episodic import episodic
from memory.knowledge_graph import knowledge_graph
from core.session import Session
import config


class PersonalityEngine:
    def __init__(self):
        self.session = Session()

    async def respond(self, user_input: str) -> str:
        """Main entry point. Classify → route → recall → generate → store."""

        if user_input.lower() in ["lock in", "lockin", "lock-in", "focus mode"]:
            self.session.mode = "lock_in"
            return "🔒 Locked in. What are we building?"
        if user_input.lower() in ["unlock", "personal mode", "relax"]:
            self.session.mode = "personal"
            return "💙 Back. What did I miss?"

        self.session.mark_active()

        query_type = self._classify(user_input)
        target_model = self._route(query_type)

        loaded = await model_manager.load_model(target_model)
        if not loaded:
            logger.warning(f"Could not load {target_model}, using current model")

        memory_context = episodic.get_context_string(user_input)
        graph_context = knowledge_graph.as_context_string("manu")

        system_prompt = identity.get_system_prompt(self.session.mode)
        if memory_context and self.session.mode == "personal":
            system_prompt += f"\n\nContext:\n{memory_context}"
        if graph_context:
            system_prompt += f"\n\n{graph_context}"

        messages = [{"role": "system", "content": system_prompt}]
        for msg in self.session.get_recent(8):
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_input})

        response = await model_manager.generate(messages)

        self.session.add_message("user", user_input, model_used=target_model, query_type=query_type)
        self.session.add_message("assistant", response, model_used=target_model)
        episodic.store("user", user_input, {"mode": self.session.mode, "query_type": query_type})
        episodic.store("assistant", response, {"mode": self.session.mode, "model": target_model})

        self._extract_facts(user_input)

        return response

    async def respond_stream(self, user_input: str):
        """Streaming version — yields tokens. Use for terminal/web UI."""
        query_type = self._classify(user_input)
        target_model = self._route(query_type)
        await model_manager.load_model(target_model)

        system_prompt = identity.get_system_prompt(self.session.mode)
        memory_context = episodic.get_context_string(user_input)
        if memory_context:
            system_prompt += f"\n\nContext:\n{memory_context}"

        messages = [{"role": "system", "content": system_prompt}]
        for msg in self.session.get_recent(8):
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_input})

        full_response = []
        async for token in model_manager.generate_stream(messages):
            full_response.append(token)
            yield token

        response = "".join(full_response)
        self.session.add_message("user", user_input)
        self.session.add_message("assistant", response)
        episodic.store("user", user_input, {"mode": self.session.mode})
        episodic.store("assistant", response, {"model": target_model})

    def _classify(self, text: str) -> str:
        t = text.lower()
        symbols = any(s in text for s in ["()", "{}", "[]", "==", "!=", "=>", "def ", "class ", "import "])
        coding_kw = ["code", "function", "debug", "error", "python", "javascript", "script", "api", "algorithm"]
        reasoning_kw = ["explain", "analyze", "why", "how does", "compare", "evaluate", "what if"]
        simple_kw = ["how are you", "hey", "hello", "hi", "morning", "night", "love you", "miss you"]

        if symbols or any(k in t for k in coding_kw):
            return "coding"
        if any(k in t for k in simple_kw) and len(text.split()) < 12:
            return "simple_chat"
        if any(k in t for k in reasoning_kw):
            return "reasoning"
        return "simple_chat"

    def _route(self, query_type: str) -> str:
        mode_key = f"{self.session.mode}_mode"
        routing = config.ROUTING_RULES.get(mode_key, {})
        default_mode = self.session.mode if self.session.mode in config.PERSONALITY_MODES else "personal"
        return routing.get(query_type, config.PERSONALITY_MODES[default_mode]["default_model"])

    def _extract_facts(self, text: str):
        t = text.lower()
        if "i am" in t or "i'm" in t:
            episodic.store_fact(text[:120], category="self_statement", importance=6)
        if "i hate" in t or "i love" in t or "i like" in t or "i don't like" in t:
            episodic.store_fact(text[:120], category="preference", importance=7)


personality_engine = PersonalityEngine()