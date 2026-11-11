"""Local LLaMA 3 inference through Ollama (FR1, FR4).

The model runs on this machine: queries never leave it. Install Ollama, then
`ollama pull llama3`, and set AI_MODE=ollama in .env.
"""
import os
import requests
from dotenv import load_dotenv
from model_base import ChatModel
from reply_format import clean_reply

load_dotenv()

OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3')
# Keep the model in memory between requests so replies stay fast.
KEEP_ALIVE = os.getenv('OLLAMA_KEEP_ALIVE', '30m')
REQUEST_TIMEOUT = int(os.getenv('OLLAMA_TIMEOUT', '300'))


class OllamaHandler(ChatModel):
    def __init__(self):
        print(f"Initializing local LLaMA 3 handler with Ollama ({OLLAMA_MODEL})...")
        # CPU-only inference runs at a few tokens per second, so replies are capped.
        super().__init__([OLLAMA_MODEL], int(os.getenv('OLLAMA_MAX_TOKENS', '256')),
                         int(os.getenv('OLLAMA_HISTORY_MESSAGES', '6')))
        self.ready = self._load_model()

    def _load_model(self):
        """Load the model into memory at startup so the first reply is not delayed (FR1)"""
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "keep_alive": KEEP_ALIVE},
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            print(f"🦙 LLaMA 3 model loaded locally: {OLLAMA_MODEL}")
            return True
        except Exception as e:
            print(f"❌ Could not load {OLLAMA_MODEL} from Ollama at {OLLAMA_URL}: {e}")
            print("   Start Ollama and run: ollama pull llama3")
            return False

    def _complete(self, model_name, messages, max_tokens, temperature):
        """One non-streaming call to the local model"""
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model_name,
                "messages": messages,
                "stream": False,
                "keep_alive": KEEP_ALIVE,
                "options": {"num_predict": max_tokens, "temperature": temperature}
            },
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        return clean_reply(data.get("message", {}).get("content")), data.get("done_reason") == "length"


llama = OllamaHandler()
