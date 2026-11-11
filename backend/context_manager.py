"""Topic-aware context window for multi-turn chat.

Each conversation keeps its turns tagged with their topic label. When the
model is called, the context is the most recent turns on the current topic
plus the immediately preceding exchange, so an unrelated earlier topic does
not pollute the reply while a follow-up such as "how does dropout help with
it?" still sees what "it" refers to. Returning to an earlier topic brings that
topic's turns back into the window.
"""


class ContextManager:
    def __init__(self, max_messages=6):
        self.max_messages = max_messages
        self.sessions = {}

    def has(self, key):
        return bool(self.sessions.get(key))

    def load(self, key, turns):
        """Rebuild a conversation from stored turns, e.g. after a server restart"""
        self.sessions[key] = self._trim(list(turns))

    def last_topic(self, key):
        turns = self.sessions.get(key)
        return turns[-1]["topic"] if turns else None

    def window(self, key, topic):
        """Chat messages to send as context for a new message on this topic"""
        turns = self.sessions.get(key, [])
        if turns and turns[-1]["topic"] != topic:
            print(f"🔀 Topic change: {turns[-1]['topic']} -> {topic}")
        last_exchange = len(turns) - 2
        keep = [turn for i, turn in enumerate(turns) if turn["topic"] == topic or i >= last_exchange]
        return [{"role": turn["role"], "content": turn["content"]} for turn in keep[-self.max_messages:]]

    def add(self, key, topic, user_message, reply):
        turns = self.sessions.setdefault(key, [])
        turns.append({"role": "user", "content": user_message, "topic": topic})
        turns.append({"role": "assistant", "content": reply, "topic": topic})
        self.sessions[key] = self._trim(turns)

    def _trim(self, turns):
        """Only the turns a window can still use: the latest max_messages per topic and the last exchange"""
        per_topic = {}
        kept = []
        for i in range(len(turns) - 1, -1, -1):
            topic = turns[i]["topic"]
            per_topic[topic] = per_topic.get(topic, 0) + 1
            if per_topic[topic] <= self.max_messages or i >= len(turns) - 2:
                kept.append(turns[i])
        return kept[::-1]

    def clear(self, key):
        self.sessions.pop(key, None)
