"""
AERIS main engine. This is what you run.
Everything starts here and runs concurrently.
"""

import asyncio
import re
import sys
from pathlib import Path

from loguru import logger

from core.bus import bus
from personality.modes import personality_engine
from personality.expression_style import apply_expression_style
from personality.voice import voice
from system.monitor import monitor
from system.feature_controller import feature_controller
from agency.cyber import cyber
from agency.tool_registry import tool_registry
from growth.idle_daemon import IdleDaemon
from growth.collector import collector
import config


logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}", level="INFO")
logger.add(config.LOGS_DIR / "aeris.log", rotation="10 MB", retention="30 days", level="DEBUG")

BANNER = """
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     █████╗ ███████╗██████╗ ██╗███████╗                  ║
║    ██╔══██╗██╔════╝██╔══██╗██║██╔════╝                  ║
║    ███████║█████╗  ██████╔╝██║███████╗                  ║
║    ██╔══██║██╔══╝  ██╔══██╗██║╚════██║                  ║
║    ██║  ██║███████╗██║  ██║██║███████║                   ║
║    ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝╚══════╝                  ║
║                                                          ║
║     v2.0  ·  Adaptive Emotional Response & Intelligence  ║
╚══════════════════════════════════════════════════════════╝
"""


def print_health(model_manager) -> None:
    from memory.episodic import episodic

    model_health = model_manager.health_snapshot()
    mem_stats = episodic.stats
    backend = config.MEMORY_CONFIG.get("embedding_backend", "unknown")

    print("\n  AERIS HEALTH")
    print(f"  Model: {model_health['model']}")
    print(f"  Adapter: {model_health['adapter']}")
    print(f"  Source: {model_health['source']}")
    print(f"  Effective n_ctx: {model_health['n_ctx']}")
    print(f"  Effective n_batch: {model_health['n_batch']}")
    print(f"  Memory backend: {backend}")
    print(f"  Memory stats: {mem_stats['conversations']} conversations, {mem_stats['facts']} facts")
    print(f"  {monitor.get_status_string()}\n")


def resolve_cyber_intent(user_text: str) -> str | None:
    text = user_text.lower().strip()

    if text in {"cyber self", "cyber home", "cyber sandbox"}:
        return text

    has_scan_word = any(w in text for w in ["scan", "map", "discover", "enumerate", "check ports", "open ports"])
    if has_scan_word and any(w in text for w in ["localhost", "127.0.0.1", "self", "my machine", "this machine", "my system"]):
        return "cyber self"

    if has_scan_word and any(w in text for w in ["home network", "local network", "lan", "subnet", "devices on network"]):
        return "cyber home"

    if any(w in text for w in ["sandbox", "docker sandbox", "container health", "sandbox test"]):
        return "cyber sandbox"

    return None


def resolve_tool_intent(user_text: str) -> tuple[str, dict] | None:
    text = user_text.strip()
    low = text.lower()

    if any(p in low for p in ["what tools do you have", "list tools", "show tools", "available tools"]):
        return "list_tools", {}

    mem_match = re.search(r"(?:search|find)\s+(?:my\s+)?memory(?:\s+for)?\s*[:\-]?\s*(.+)", text, flags=re.IGNORECASE)
    if mem_match:
        query = mem_match.group(1).strip()
        if query:
            return "memory_search", {"query": query}

    shorthand_mem_match = re.search(r"^(?:memory|recall|remember)\s+(.+)$", text, flags=re.IGNORECASE)
    if shorthand_mem_match:
        query = shorthand_mem_match.group(1).strip()
        if query:
            return "memory_search", {"query": query}

    about_mem_match = re.search(r"(?:what\s+do\s+you\s+remember\s+about|remember\s+about)\s+(.+)$", text, flags=re.IGNORECASE)
    if about_mem_match:
        query = about_mem_match.group(1).strip()
        if query:
            return "memory_search", {"query": query}

    fetch_match = re.search(r"\bfetch\b\s+(https?://\S+)", text, flags=re.IGNORECASE)
    if fetch_match:
        return "web_fetch", {"url": fetch_match.group(1)}

    read_match = re.search(r"\bread\s+file\b\s+(.+)", text, flags=re.IGNORECASE)
    if read_match:
        path = read_match.group(1).strip().strip('"').strip("'")
        if path:
            return "read_file", {"path": path}

    return None


def resolve_policy_intent(user_text: str) -> str | None:
    text = user_text.lower().strip()
    if text in {"policy", "policy status", "feature policy", "mode policy"}:
        return "status"
    if any(k in text for k in ["balanced policy", "policy balanced", "normal policy"]):
        return "balanced"
    if any(k in text for k in ["full online", "always online", "policy full", "policy full online"]):
        return "full_online"
    if any(k in text for k in ["aggressive save", "eco mode", "save memory", "policy eco"]):
        return "eco"
    return None


async def main():
    print(BANNER)
    print(f"\n  {monitor.get_status_string()}\n")

    bus.initialize()
    asyncio.create_task(bus.run())
    await feature_controller.startup()
    
    # Start the idle daemon — AERIS lives even when Manu is away
    idle_daemon = IdleDaemon(engine_ref=None)
    idle_daemon.start()

    from inference.model_manager import model_manager

    model_manager.refresh_adapter()

    loaded = await model_manager.load_model(config.PERSONALITY_MODES["personal"]["default_model"])
    if not loaded:
        print("[FATAL] Could not load default model. Check model paths in config.py")
        return

    wake_msg = await personality_engine.respond("AERIS_INIT: System started. Greet Manu and tell him what you remember.")
    wake_msg = apply_expression_style(wake_msg, personality_engine.session.mode)
    print(f"\nAERIS: {wake_msg}\n")
    Path("/tmp/aeris_mode").write_text(personality_engine.session.mode, encoding="utf-8")
    Path("/tmp/aeris_last_msg").write_text(wake_msg[:80], encoding="utf-8")
    print_health(model_manager)
    print("─" * 60)
    print("  'lock in' / 'unlock'  ·  'status'  ·  'memory'  ·  'health'  ·  'features'  ·  'feature web on/off'  ·  'feature widget on/off'  ·  'autopilot on/off'  ·  'policy status/balanced/full_online/eco'  ·  'cyber self/home/sandbox'  ·  'voice on/off/status'  ·  'quit'")
    print("─" * 60 + "\n")

    voice_enabled = False
    daemon_mode = False
    if not sys.stdin.isatty():
        logger.info("No interactive stdin detected; running in daemon mode")

    while True:
        try:
            if daemon_mode:
                auto_note = await feature_controller.autopilot_tick(personality_engine.session.mode)
                if auto_note:
                    logger.info(auto_note)
                await asyncio.sleep(60)
                continue

            user_input = input("Manu: ").strip()
            if not user_input:
                continue

            quality_cmd = user_input.lower()
            if quality_cmd in {"/good", "good answer", "that was good"}:
                collector.mark_last_good()
                print("\nAERIS: Noted. I'll reinforce that style. ✅\n")
                continue
            if quality_cmd in {"/bad", "bad answer", "that was bad"}:
                collector.mark_last_bad()
                print("\nAERIS: Noted. I'll avoid that pattern. 🔍\n")
                continue

            feedback_signal = collector.observe_user_feedback(user_input)
            if feedback_signal == "good" and len(user_input.split()) <= 5:
                print("\nAERIS: Got it. I'll keep that style. ✅\n")
                continue
            if feedback_signal == "bad" and len(user_input.split()) <= 6:
                print("\nAERIS: Understood. I'll correct course. Say it again and I'll answer better. 🔧\n")
                continue

            cyber_intent = resolve_cyber_intent(user_input)
            if cyber_intent == "cyber self":
                result = await cyber.scan_self()
                print(f"\nAERIS: {result}\n")
                continue
            if cyber_intent == "cyber home":
                result = await cyber.scan_home_network()
                print(f"\nAERIS: {result}\n")
                continue
            if cyber_intent == "cyber sandbox":
                result = await cyber.run_sandbox_escape_test()
                print(f"\nAERIS: {result}\n")
                continue

            tool_intent = resolve_tool_intent(user_input)
            if tool_intent:
                tool_name, tool_params = tool_intent
                if tool_name == "list_tools":
                    tool_output = tool_registry.list_tools()
                else:
                    tool_output = await tool_registry.execute(tool_name, tool_params)
                print(f"\nAERIS (tool): {tool_output}\n")
                continue

            policy_intent = resolve_policy_intent(user_input)
            if policy_intent == "status":
                print(f"\nAERIS: {feature_controller.policy_status()}\n")
                continue
            if policy_intent in {"balanced", "full_online", "eco"}:
                print(f"\nAERIS: {feature_controller.set_policy_profile(policy_intent)}\n")
                continue

            if user_input.lower() == "what did you do":
                print(f"\nAERIS: {idle_daemon.get_report()}\n")
                continue

            if user_input.lower() == "features":
                print(f"\nAERIS: {feature_controller.status_string()}\n")
                continue

            if user_input.lower() == "feature web on":
                result = await feature_controller.ensure_web_online()
                print(f"\nAERIS: {result}\n")
                continue

            if user_input.lower() == "feature web off":
                result = await feature_controller.stop_web()
                print(f"\nAERIS: {result}\n")
                continue

            if user_input.lower() == "feature widget on":
                result = feature_controller.ensure_widget_online()
                print(f"\nAERIS: {result}\n")
                continue

            if user_input.lower() == "feature widget off":
                result = feature_controller.close_widget()
                print(f"\nAERIS: {result}\n")
                continue

            if user_input.lower() == "autopilot on":
                print(f"\nAERIS: {feature_controller.set_autopilot(True)}\n")
                continue

            if user_input.lower() == "autopilot off":
                print(f"\nAERIS: {feature_controller.set_autopilot(False)}\n")
                continue

            if user_input.lower().startswith("policy "):
                profile = user_input[7:].strip()
                if profile:
                    print(f"\nAERIS: {feature_controller.set_policy_profile(profile)}\n")
                    continue

            if user_input.lower() == "quit":
                print("\nAERIS: See you soon. 💙")
                idle_daemon.stop()
                await feature_controller.shutdown()
                break
            elif user_input.lower() == "status":
                print(f"\n  Mode: {personality_engine.session.mode}")
                print(f"  Model: {model_manager.current_model_name}")
                print(f"  {monitor.get_status_string()}")
                from memory.episodic import episodic
                s = episodic.stats
                print(f"  Memory: {s['conversations']} conversations, {s['facts']} facts\n")
                continue
            elif user_input.lower() == "memory":
                from memory.episodic import episodic
                mems = episodic.recall(user_input, n=5)
                print("\n  Recent memories:")
                for m in mems:
                    print(f"    [{m['metadata'].get('role','?')}] {m['content'][:80]}")
                print()
                continue
            elif user_input.lower() == "health":
                print_health(model_manager)
                continue
            elif user_input.lower() == "voice on":
                voice_enabled = True
                print("\nAERIS: Voice output enabled. I'll speak my replies when possible. 🔊\n")
                continue
            elif user_input.lower() == "voice off":
                voice_enabled = False
                print("\nAERIS: Voice output disabled. 🔇\n")
                continue
            elif user_input.lower() == "voice status":
                print(f"\nAERIS: Voice output is {'ON' if voice_enabled else 'OFF'}.\n")
                continue
            elif user_input.lower().startswith("speak "):
                manual_text = user_input[6:].strip()
                if manual_text:
                    await voice.speak(manual_text)
                continue

            print("\nAERIS: ", end="", flush=True)
            response_parts = []
            async for token in personality_engine.respond_stream(user_input):
                print(token, end="", flush=True)
                response_parts.append(token)
            response_raw = "".join(response_parts).strip()
            response = apply_expression_style(response_raw, personality_engine.session.mode)
            if response.startswith(response_raw):
                extra = response[len(response_raw):]
                if extra:
                    print(extra, end="", flush=True)
            print("\n")

            if voice_enabled:
                await voice.speak(response)

            auto_note = await feature_controller.autopilot_tick(personality_engine.session.mode)
            if auto_note:
                logger.info(auto_note)

            Path("/tmp/aeris_mode").write_text(personality_engine.session.mode, encoding="utf-8")
            Path("/tmp/aeris_last_msg").write_text(response[:80], encoding="utf-8")
            collector.record(
                user_input=user_input,
                response=response,
                model=model_manager.current_model_name or "unknown",
            )

        except KeyboardInterrupt:
            print("\n\nAERIS: Still here. 💙")
            collector.flush()
            idle_daemon.stop()
            await feature_controller.shutdown()
            break
        except EOFError:
            logger.info("stdin closed; switching to daemon mode")
            daemon_mode = True
            continue
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            print(f"\n[Error: {e}]\n")
    collector.flush()


if __name__ == "__main__":
    asyncio.run(main())