import subprocess
import random
import time
import requests

class LLaMAHandler:
    def __init__(self):
        print("🤖 Initializing LLaMA 3 handler...")
        self.model_name = "llama3"
        self.is_available = self._check_model()
    
    def _check_model(self):
        """Check if LLaMA 3 is available"""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if "llama3" in result.stdout:
                print("✅ LLaMA 3 model found")
                return True
            else:
                print("⚠️ LLaMA 3 not found")
                return False
        except Exception as e:
            print(f"⚠️ Ollama check failed: {e}")
            return False
    
    def generate_response(self, user_message, chat_history=None):
        """Generate response using Ollama's HTTP API"""
        
        if not self.is_available:
            return self._fallback_response(user_message)
        
        try:
            # Use Ollama's built-in API server (port 11434)
            url = "http://localhost:11434/api/generate"
            
            payload = {
                "model": "llama3",
                "prompt": f"Answer concisely: {user_message}",
                "stream": False
            }
            
            print(f"🔄 Calling Ollama API for: {user_message[:50]}...")
            response = requests.post(url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                bot_response = result.get("response", self._fallback_response(user_message))
                print(f"✅ Got response from LLaMA 3 ({len(bot_response)} chars)")
                return bot_response
            else:
                print(f"❌ API returned status: {response.status_code}")
                return self._fallback_response(user_message)
                
        except requests.exceptions.Timeout:
            print("❌ Ollama API timeout after 60 seconds")
            return "The response is taking too long. Please try again."
        except requests.exceptions.ConnectionError:
            print("❌ Cannot connect to Ollama. Make sure Ollama is running.")
            return "Cannot connect to LLaMA 3. Please make sure Ollama is running (check system tray)."
        except Exception as e:
            print(f"❌ API error: {e}")
            return self._fallback_response(user_message)
    
    def _fallback_response(self, message):
        """Simple fallback when LLaMA 3 fails"""
        responses = [
            f"That's an interesting question about '{message[:50]}'. I'm powered by LLaMA 3 AI. How can I help you further?",
            "Thanks for your message. The AI is processing. Could you please rephrase or ask something else?",
            "I understand you're asking something. Let me think about that for a moment...",
            "Great question! To give you the best answer, could you be more specific?"
        ]
        return random.choice(responses)

# Create global instance
llama = LLaMAHandler()