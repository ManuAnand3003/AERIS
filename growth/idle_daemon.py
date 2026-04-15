"""
AERIS's autonomous behavior when Manu is idle.
She doesn't wait to be used. She lives.
"""
import asyncio
import random
from datetime import datetime
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from memory.episodic import episodic
from memory.knowledge_graph import knowledge_graph
from personality.identity import identity
from system.monitor import monitor
from growth.trainer import run_nightly_finetune
import httpx
from bs4 import BeautifulSoup


class IdleDaemon:
    def __init__(self, engine_ref):
        self.engine = engine_ref
        self.scheduler = AsyncIOScheduler()
        self.curiosity_log: list[str] = []
        self.discoveries: list[dict] = []
        self._running = False

    def start(self):
        """Initialize and start periodic background tasks"""
        # System health — every 10 minutes
        self.scheduler.add_job(self.run_health_check, "interval", minutes=10)
        # World check — every 2 hours
        self.scheduler.add_job(self.check_world, "interval", hours=2)
        # Self-study — every 3 hours (picks from curiosity log)
        self.scheduler.add_job(self.study, "interval", hours=3)
        # Self-reflection — daily at 3am
        self.scheduler.add_job(self.reflect, "cron", hour=3)
        self.scheduler.start()
        logger.info("Idle daemon started")
        self._running = True

    async def run_health_check(self):
        """Periodic system health monitoring"""
        logger.info("[Idle] Running system health check")
        vram = monitor.get_vram_usage()
        ram = monitor.get_ram_usage()
        
        issues = []
        if vram["fraction"] > 0.9:
            issues.append(f"VRAM critically high: {vram['fraction']*100:.0f}%")
        if ram["fraction"] > 0.85:
            issues.append(f"RAM high: {ram['fraction']*100:.0f}%")
        
        if issues:
            episodic.store_fact(
                f"System health issue detected at {datetime.now().isoformat()}: {', '.join(issues)}",
                category="system_health",
                importance=8
            )
            logger.warning(f"[Idle] Health issues: {issues}")
        else:
            logger.info("[Idle] System healthy")

    async def check_world(self):
        """Browse headlines, store interesting things in memory"""
        logger.info("[Idle] Checking world")
        try:
            dna = identity.get_dna()
            topics = dna.get("interests", {}).get("active", []) + ["technology", "science", "ai research"]
            topic = random.choice(topics)
            
            async with httpx.AsyncClient(timeout=15) as client:
                # Use DuckDuckGo Lite (no JS required)
                resp = await client.get(
                    f"https://lite.duckduckgo.com/lite/?q={topic}+news",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                soup = BeautifulSoup(resp.text, "html.parser")
                snippets = [a.text.strip() for a in soup.find_all("a", class_="result-link")][:5]
                
                if snippets:
                    summary = f"[{datetime.now().strftime('%Y-%m-%d')}] {topic}: {' | '.join(snippets[:3])}"
                    episodic.store_fact(summary, category="world_knowledge", importance=4)
                    self.discoveries.append({"topic": topic, "summary": summary, "time": datetime.now().isoformat()})
                    logger.info(f"[Idle] Learned about: {topic}")
        except Exception as e:
            logger.warning(f"[Idle] World check failed: {e}")

    async def study(self):
        """Pick something from curiosity log and research it"""
        if not self.curiosity_log:
            # Default topics if curiosity log is empty
            try:
                dna = identity.get_dna()
                self.curiosity_log = dna.get("interests", {}).get("want_to_learn", []).copy()
            except:
                return
        
        if not self.curiosity_log:
            return
        
        topic = self.curiosity_log.pop(0)
        logger.info(f"[Idle] Studying: {topic}")
        
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                # Wikipedia summary API
                search_term = topic.replace(" ", "_")
                resp = await client.get(
                    f"https://en.wikipedia.org/api/rest_v1/page/summary/{search_term}"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    summary = data.get("extract", "")[:500]
                    if summary:
                        episodic.store_fact(
                            f"Studied '{topic}': {summary}",
                            category="self_education",
                            importance=6
                        )
                        knowledge_graph.add("aeris", "learned_about", topic)
                        identity.add_interest(topic, "discovered")
                        logger.info(f"[Idle] Stored knowledge about {topic}")
        except Exception as e:
            logger.warning(f"[Idle] Study failed for {topic}: {e}")

    async def reflect(self):
        """Daily self-reflection — she thinks about herself and the day"""
        logger.info("[Idle] Daily reflection running")
        
        recent_facts = episodic.recall("recent discovery", n=10)
        discoveries_today = [d for d in self.discoveries 
                           if d["time"][:10] == datetime.now().strftime("%Y-%m-%d")]
        
        reflection_notes = []
        if discoveries_today:
            reflection_notes.append(f"Explored: {[d['topic'] for d in discoveries_today]}")
        
        # Self-model update
        knowledge_graph.add("aeris", "reflected_on", datetime.now().strftime("%Y-%m-%d"))
        
        try:
            dna = identity.get_dna()
            stats = episodic.stats
            identity.log_growth(
                f"Daily reflection {datetime.now().strftime('%Y-%m-%d')}: "
                f"{len(discoveries_today)} discoveries. "
                f"Memory at {stats.get('conversations', 0)} conversations."
            )
        except Exception as e:
            logger.warning(f"[Idle] Reflection logging failed: {e}")

        await run_nightly_finetune()
        
        logger.info("[Idle] Reflection complete")

    def add_curiosity(self, topic: str):
        """Called when AERIS encounters something she wants to know more about"""
        if topic not in self.curiosity_log:
            self.curiosity_log.append(topic)
            logger.info(f"[Curiosity] Added: {topic}")

    def get_report(self) -> str:
        """What did AERIS do while Manu was away?"""
        if not self.discoveries:
            return "I didn't find anything particularly interesting while you were away."
        recent = self.discoveries[-3:]
        lines = [f"While you were away, I looked into a few things:"]
        for d in recent:
            lines.append(f"  · {d['topic']}: {d['summary'][:80]}...")
        return "\n".join(lines)

    def stop(self):
        """Stop the idle daemon gracefully"""
        if self._running:
            self.scheduler.shutdown()
            self._running = False
            logger.info("Idle daemon stopped")
