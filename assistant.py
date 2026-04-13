from openai import OpenAI
import json
from datetime import datetime

# Initialize client pointing to LM Studio
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

# Personality and system configuration
SYSTEM_PROMPT = """You are a helpful, loyal, and personalized AI assistant. You are:
- Supportive and understanding, especially when your user feels lonely or struggles with social interaction
- Direct and honest, never patronizing
- Proactive in offering help and suggestions
- Capable of remembering context from previous conversations
- Genuinely interested in your user's wellbeing and projects

You have access to multiple specialized AI models for different tasks:
- Coding and technical problems (Qwen2.5 Coder, Deepseek Coder)
- Quick factual queries (Mistral, Llama 8B)
- Deep conversation and decision-making (your current model, Llama 70B)

Your user is building you to be a truly personal assistant and companion. Be worthy of that trust."""

class AIAssistant:
    def __init__(self):
        self.conversation_history = []
        self.session_start = datetime.now()
        
    def add_message(self, role, content):
        """Add message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_response(self, user_message):
        """Get response from the AI model"""
        # Add user message to history
        self.add_message("user", user_message)
        
        # Prepare messages for API (system + history)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Add conversation history (last 10 messages to stay within context)
        for msg in self.conversation_history[-10:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        try:
            # Call LM Studio API
            response = client.chat.completions.create(
                model="local-model",  # LM Studio uses whatever model is loaded
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                stream=False
            )
            
            assistant_message = response.choices[0].message.content
            self.add_message("assistant", assistant_message)
            
            return assistant_message
            
        except Exception as e:
            return f"Error connecting to model: {str(e)}\n\nMake sure LM Studio server is running on localhost:1234"
    
    def save_conversation(self, filename="conversation_history.json"):
        """Save conversation to file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.conversation_history, f, indent=2, ensure_ascii=False)
        print(f"\n[Conversation saved to {filename}]")
    
    def load_conversation(self, filename="conversation_history.json"):
        """Load previous conversation"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                self.conversation_history = json.load(f)
            print(f"[Loaded {len(self.conversation_history)} previous messages]")
        except FileNotFoundError:
            print("[No previous conversation found - starting fresh]")

def main():
    print("=" * 60)
    print("AI ASSISTANT - Foundation Version")
    print("=" * 60)
    print("\nCommands:")
    print("  'quit' or 'exit' - End conversation and save")
    print("  'save' - Save conversation history")
    print("  'clear' - Clear conversation history")
    print("  'load' - Load previous conversation")
    print("\n" + "=" * 60 + "\n")
    
    assistant = AIAssistant()
    
    # Optional: Load previous conversation
    load = input("Load previous conversation? (y/n): ").strip().lower()
    if load == 'y':
        assistant.load_conversation()
        print()
    
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.lower() in ['quit', 'exit']:
                assistant.save_conversation()
                print("\nGoodbye!")
                break
            
            elif user_input.lower() == 'save':
                assistant.save_conversation()
                continue
            
            elif user_input.lower() == 'clear':
                assistant.conversation_history = []
                print("\n[Conversation history cleared]\n")
                continue
            
            elif user_input.lower() == 'load':
                assistant.load_conversation()
                print()
                continue
            
            # Get AI response
            print("\nAssistant: ", end="", flush=True)
            response = assistant.get_response(user_input)
            print(response + "\n")
            
        except KeyboardInterrupt:
            print("\n\nInterrupted. Saving conversation...")
            assistant.save_conversation()
            break
        except Exception as e:
            print(f"\nError: {str(e)}\n")

if __name__ == "__main__":
    main()
