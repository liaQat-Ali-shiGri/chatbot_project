"""Groq API handler (AI_MODE=groq), an alternative to the local LLaMA 3 handler.

Each request tries the primary model first and falls back to the next model
only if it fails, so a temporary error never leaves the chatbot stuck on a
fallback.
"""
from datetime import datetime
from groq import Groq
import os
from dotenv import load_dotenv
from model_base import ChatModel
from reply_format import clean_reply

load_dotenv()

# Models Groq currently serves; override with a comma-separated GROQ_FALLBACK_MODELS in .env.
DEFAULT_FALLBACK_MODELS = "openai/gpt-oss-120b,qwen/qwen3.8-27b"
SYSTEM_PROMPT = ("You are a helpful AI assistant. Answer the user's latest message directly and accurately. "
                 "Do not repeat the user's question. Never show hidden reasoning, analysis, or <think> tags; "
                 "provide only the final answer.")


class MultiModelHandler(ChatModel):
    # Reasoning models spend part of a label's budget thinking before they answer.
    label_tokens = 256

    def __init__(self):
        print("Initializing Multi-Model Handler with Groq API...")
        self.client = Groq(api_key=os.getenv('GROQ_API_KEY'))
        fallbacks = os.getenv('GROQ_FALLBACK_MODELS', DEFAULT_FALLBACK_MODELS).split(',')
        super().__init__(
            [os.getenv('GROQ_PRIMARY_MODEL', 'openai/gpt-oss-20b')] + [name.strip() for name in fallbacks if name.strip()],
            # Reasoning models spend part of this budget thinking, so it must leave room for the answer.
            int(os.getenv('GROQ_MAX_TOKENS', '1024')),
            int(os.getenv('GROQ_HISTORY_MESSAGES', '6')),
        )
        print(f"🟢 Primary model: {self.model_names[0]}")

    def _messages(self, context, user_message):
        realtime = f"Current date and time: {datetime.now().strftime('%Y-%m-%d, %I:%M %p')}. "
        return [{"role": "system", "content": SYSTEM_PROMPT}, *context,
                {"role": "user", "content": realtime + user_message}]

    def _complete(self, model_name, messages, max_tokens, temperature):
        # Hide reasoning from the reply; gpt-oss models also keep it short so the answer fits.
        options = {"include_reasoning": False}
        if "gpt-oss" in model_name:
            options["reasoning_effort"] = "low"
        completion = self.client.chat.completions.create(
            model=model_name, messages=messages, temperature=temperature, max_tokens=max_tokens, **options
        )
        choice = completion.choices[0]
        return clean_reply(choice.message.content), choice.finish_reason == "length"


llama = MultiModelHandler()
