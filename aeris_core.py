"""
AERIS - Core Application
Your forever AI companion and personal assistant

Usage:
    python aeris_core.py
    
Commands:
    'lock in' - Switch to work mode
    'unlock' - Return to personal mode
    'status' - Show system status
    'memory' - Show memory stats
    'export' - Export conversation history
    'clear' - Clear screen
    'quit' - Exit and save
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

import config
from personality import get_personality_system
from model_manager import get_model_manager
from memory_system import get_memory_system

class AERIS:
    def __init__(self):
        self.banner = """
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     █████╗ ███████╗██████╗ ██╗███████╗                 ║
║    ██╔══██╗██╔════╝██╔══██╗██║██╔════╝                 ║
║    ███████║█████╗  ██████╔╝██║███████╗                 ║
║    ██╔══██║██╔══╝  ██╔══██╗██║╚════██║                 ║
║    ██║  ██║███████╗██║  ██║██║███████║                 ║
║    ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝╚══════╝                 ║
║                                                          ║
║           Your Forever AI Companion                      ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"""
        self.personality = None
        self.model_manager = None
        self.memory = None
        self.session_start = datetime.now()
        
    def initialize(self):
        """Initialize all systems"""
        print(self.banner)
        print("\n[Initializing AERIS systems...]")
        print(f"[Session started: {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}]\n")
        
        try:
            # Initialize components
            self.personality = get_personality_system()
            self.model_manager = get_model_manager()
            self.memory = get_memory_system()
            
            # Load default model
            print("\n[Loading default personality model...]")
            default_model = config.PERSONALITY_MODES["personal"]["default_model"]
            self.model_manager.load_model(default_model)
            
            print("\n" + "="*60)
            print("✓ AERIS is ready")
            print("="*60)

            # Generate welcome without streaming
            for response in self.personality.generate_response("Hi AERIS! It's me, your creator. I'm here.", stream=False):
                welcome = response
                break
            print(f"\nAERIS: {welcome}\n")
            
            return True
            
        except Exception as e:
            print(f"\n[✗ Initialization error: {e}]")
            print("\nPlease check:")
            print("1. Model paths in config.py are correct")
            print("2. Model files exist in D:\\prompt-lab\\models")
            print("3. All dependencies are installed")
            return False
    
    def show_help(self):
        """Show available commands"""
        help_text = """
╔══════════════════════════════════════════════════════════╗
║                    AERIS COMMANDS                        ║
╠══════════════════════════════════════════════════════════╣
║  Mode Switching:                                         ║
║    'lock in'      - Switch to focused work mode          ║
║    'unlock'       - Return to personal mode              ║
║                                                          ║
║  System:                                                 ║
║    'status'       - Show current system status           ║
║    'memory'       - Show memory statistics               ║
║    'models'       - List available models                ║
║    'export'       - Export conversation history          ║
║                                                          ║
║  Utility:                                                ║
║    'clear'        - Clear screen                         ║
║    'help'         - Show this help                       ║
║    'quit'         - Exit and save session                ║
╚══════════════════════════════════════════════════════════╝
"""
        print(help_text)
    
    def show_status(self):
        """Show system status"""
        status = self.personality.get_status()
        
        print("\n╔═══════════════════ SYSTEM STATUS ═══════════════════╗")
        print(f"║ Mode: {status['mode'].upper()}")
        print(f"║ Current Model: {status['current_model']['name']}")
        print(f"║   Role: {status['current_model']['role']}")
        print(f"║   Speed: {status['current_model']['speed']}")
        print(f"║ Conversation Length: {status['conversation_length']} messages")
        print(f"║ Total Memories: {status['memory']['total_conversations']}")
        print(f"║ Facts Known: {status['memory']['total_facts']}")
        print(f"║ Session Duration: {self._get_session_duration()}")
        print("╚═══════════════════════════════════════════════════════╝\n")
    
    def show_memory_stats(self):
        """Show memory statistics"""
        stats = self.memory.get_stats()
        
        print("\n╔═══════════════════ MEMORY STATS ════════════════════╗")
        print(f"║ Total Conversations: {stats['total_conversations']}")
        print(f"║ Facts Remembered: {stats['total_facts']}")
        print(f"║ Storage: {stats['storage_path']}")
        print("╚═══════════════════════════════════════════════════════╝\n")
        
        # Show recent memories
        recent = self.memory.remember("recent conversation", n_results=3)
        if recent:
            print("Recent memories:")
            for i, mem in enumerate(recent, 1):
                role = mem['metadata'].get('role', 'unknown')
                content = mem['content'][:80] + "..." if len(mem['content']) > 80 else mem['content']
                print(f"  {i}. [{role}] {content}")
            print()
    
    def list_models(self):
        """List all available models"""
        models = self.model_manager.list_available_models()
        
        print("\n╔═══════════════════ AVAILABLE MODELS ════════════════╗")
        for model in models:
            status = "✓" if model["available"] else "✗"
            current = "◄ LOADED" if model["name"] == self.model_manager.current_model_name else ""
            print(f"║ {status} {model['name']:<25} │ {model['role']:<20} │ {model['speed']:<8} {current}")
        print("╚═══════════════════════════════════════════════════════╝\n")
    
    def export_conversations(self):
        """Export conversation history"""
        print("\n[Exporting conversation history...]")
        file_path = self.memory.export_conversations()
        if file_path:
            print(f"[✓ Saved to: {file_path}]\n")
        else:
            print("[✗ Export failed]\n")
    
    def _get_session_duration(self):
        """Get current session duration"""
        duration = datetime.now() - self.session_start
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        seconds = duration.seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def run(self):
        """Main application loop"""
        
        if not self.initialize():
            return
        
        print("\nType 'help' for commands, or just chat with me naturally 💙\n")
        
        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.lower() == 'quit':
                    print("\n[Saving session...]")
                    print(f"AERIS: Until next time 💙 Take care of yourself.")
                    print(f"\n[Session duration: {self._get_session_duration()}]")
                    break
                
                elif user_input.lower() == 'help':
                    self.show_help()
                    continue
                
                elif user_input.lower() == 'status':
                    self.show_status()
                    continue
                
                elif user_input.lower() == 'memory':
                    self.show_memory_stats()
                    continue
                
                elif user_input.lower() == 'models':
                    self.list_models()
                    continue
                
                elif user_input.lower() == 'export':
                    self.export_conversations()
                    continue
                
                elif user_input.lower() == 'clear':
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print(self.banner)
                    continue
                
                # Generate AERIS response
                print("\nAERIS: ", end="", flush=True)
                response = self.personality.generate_response(user_input, stream=False)
                print(response + "\n")
                
            except KeyboardInterrupt:
                print("\n\n[Interrupted]")
                save = input("Save session before exiting? (y/n): ").lower()
                if save == 'y':
                    print("[Saving...]")
                break
                
            except Exception as e:
                print(f"\n[Error: {e}]")
                print("Let's try that again.\n")


def main():
    """Entry point"""
    aeris = AERIS()
    aeris.run()


if __name__ == "__main__":
    main()
