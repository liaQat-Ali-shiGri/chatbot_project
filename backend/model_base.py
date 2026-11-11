"""Reply and label handling shared by the local LLaMA 3 and Groq handlers.

A handler only supplies how one completion is requested (_complete) and, if it
needs more than the context window and the question, how the prompt is built
(_messages). Each request tries the first model and falls back to the next one
only if it fails.
"""
from context_manager import ContextManager
from reply_format import LENGTH_NOTE


class ChatModel:
    # Token budget for chat titles and question subjects
    label_tokens = 20

    def __init__(self, model_names, max_tokens, history_messages):
        self.model_names = model_names
        self.active_model = model_names[0]
        self.max_tokens = max_tokens
        self.context = ContextManager(history_messages)
        self.ready = True

    def _complete(self, model_name, messages, max_tokens, temperature):
        """One completion: (reply without hidden reasoning, whether it hit the length limit)"""
        raise NotImplementedError

    def _messages(self, context, user_message):
        # The user's query is sent as typed, with the topic-aware context window before it.
        return [*context, {"role": "user", "content": user_message}]

    def generate_label(self, prompt):
        """A short, context-free completion used to name a chat or a question"""
        try:
            label, _ = self._complete(self.model_names[0], [{"role": "user", "content": prompt}], self.label_tokens, 0.2)
            return label
        except Exception as e:
            print(f"❌ Label generation failed with {self.model_names[0]}: {e}")
            return None

    def generate_response(self, user_message, session_id="default", topic=None):
        """The model's reply, or None if every model failed"""
        context = self.context.window(session_id, topic)
        messages = self._messages(context, user_message)
        for name in self.model_names:
            try:
                print(f"⏳ Calling {name} with {len(context)} context messages on topic {topic}")
                result, truncated = self._complete(name, messages, self.max_tokens, 0.3)
                if not result:
                    raise RuntimeError("empty response")
                if truncated:
                    result += LENGTH_NOTE
                self.context.add(session_id, topic, user_message, result)
                self.active_model = name
                self.ready = True
                print(f"✅ Response received ({len(result)} chars)")
                return result
            except Exception as e:
                print(f"❌ {name} error: {e}")
        self.ready = False
        return None
