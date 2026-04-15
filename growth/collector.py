"""
Collects interaction data for fine-tuning.
Watches for implicit feedback: if Manu corrects a response or
rephrases the question, the previous response was bad.
"""

import json
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher

from loguru import logger

import config


TRAINING_DATA_DIR = config.DATA_DIR / "training"
TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)


class InteractionCollector:
    def __init__(self):
        self.pending: list[dict] = []
        self.last_exchange: dict | None = None

    def record(self, user_input: str, response: str, model: str, quality: float = 0.5):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user": user_input,
            "assistant": response,
            "model": model,
            "quality": quality,  # 0.0 = bad, 1.0 = good
        }
        self.last_exchange = entry
        self.pending.append(entry)

        if len(self.pending) >= 50:
            self.flush()

    def mark_last_good(self):
        if self.last_exchange:
            self.last_exchange["quality"] = 1.0

    def mark_last_bad(self):
        if self.last_exchange:
            self.last_exchange["quality"] = 0.1

    def observe_user_feedback(self, user_input: str) -> str | None:
        """Infer implicit quality signals from the next user message."""
        if not self.last_exchange:
            return None

        text = user_input.strip().lower()
        if not text:
            return None

        praise_markers = [
            "good answer",
            "nice",
            "great",
            "perfect",
            "exactly",
            "thanks",
            "that helps",
        ]
        correction_markers = [
            "that's wrong",
            "you are wrong",
            "not what i asked",
            "no,",
            "incorrect",
            "wrong",
            "try again",
            "rephrase",
            "redo",
        ]

        if any(marker in text for marker in praise_markers):
            self.mark_last_good()
            return "good"

        if any(marker in text for marker in correction_markers):
            self.mark_last_bad()
            return "bad"

        prev_user = str(self.last_exchange.get("user", "")).strip().lower()
        if prev_user and len(text.split()) >= 4:
            similarity = SequenceMatcher(None, prev_user, text).ratio()
            if similarity >= 0.78 and text != prev_user:
                # Re-asking with a very similar prompt usually means the previous reply missed.
                self.mark_last_bad()
                return "bad_rephrase"

        return None

    def flush(self):
        if not self.pending:
            return
        out_file = TRAINING_DATA_DIR / f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(self.pending, f, indent=2)
        logger.info(f"Flushed {len(self.pending)} interactions to {out_file}")
        self.pending = []


collector = InteractionCollector()
