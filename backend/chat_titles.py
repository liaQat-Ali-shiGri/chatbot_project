"""Short labels written by the chat model in a background worker.

- Chat titles name the main point of each chat session. A session is titled
  after its first reply and re-titled from the whole conversation when it ends;
  older sessions without a title are queued when the chat history loads.
- Subjects name what each question is about in 1-4 words ("Literacy Rate",
  "Overfitting"). The topic classifier puts a question in one of the five AI
  domains or General; the subject says specifically what was asked, also for
  questions outside those domains.

Labels never delay a reply: the worker waits while a reply is being generated.
Until a label arrives, a cleaned-up version of the question is shown instead.
"""
import itertools
import queue
import re
import threading
import time
from reply_format import clean_reply

TITLE_PROMPT = (
    "Here is a chat between a user and an AI assistant:\n\n{chat}\n\n"
    "Name the main topic of this chat as a short heading of 1 to 4 words.\n"
    "Rules:\n"
    "- Use the user's own words. If the user wrote an acronym such as AI, AGI or ASI, "
    "use that acronym exactly and do not expand it.\n"
    "- Correct spelling mistakes.\n"
    "- Combine related ideas into one heading.\n"
    "Examples:\n"
    "\"what is AGI?\" -> AGI\n"
    "\"hi what is ASI?\" -> ASI\n"
    "\"How do hospitals use AI for diagnosis?\" -> AI in Healthcare\n"
    "\"What is artificial intellegence?\" -> Artificial Intelligence\n"
    "\"What health issues are there worldwide?\" -> Worldwide Health Issues\n"
    "Reply with the heading only, without quotes or a full stop."
)
SUBJECT_PROMPT = (
    "A user asked an AI chatbot this question:\n\n\"{question}\"\n\n{previous}"
    "Name the subject of the question as a short heading of 1 to 4 words.\n"
    "Rules:\n"
    "- Name the thing being asked about, not the type of question.\n"
    "- Keep any acronym the user wrote (AI, AGI, ASI) and do not expand it.\n"
    "- Correct spelling mistakes.\n"
    "- If the question is a follow-up, read it together with the previous question: keep the previous "
    "subject when it asks more about it. When it moves to a new place or field, keep the method or "
    "technology from the previous question and add the new place or field.\n"
    "Examples:\n"
    "\"What is the literacy rate in the developed countries?\" -> Literacy Rate\n"
    "\"What is AI?\" -> AI\n"
    "\"What is overfitting and how can I prevent it?\" -> Overfitting\n"
    "\"How do online stores recommend products?\" -> Product Recommendations\n"
    "\"Can you give an example?\" after \"What is a smart grid?\" -> Smart Grid\n"
    "\"What about farming?\" after \"How can drones be used in construction?\" -> Drones in Farming\n"
    "Reply with the heading only, without quotes or a full stop."
)
# Spacing between background labels keeps them within the model's rate limits.
PAUSE_SECONDS = 2
RETRY_AFTER_SECONDS = 600
MAX_QUESTIONS = 8
MISSING_SUBJECTS_BATCH = 100
# Titles go first: the chat history waits for them, while subjects are only used by the dashboard.
PRIORITY = {"title": 0, "subject": 1}

QUESTION_START = re.compile(
    r"^(?:(?:hi|hello|hey|salam|assalam\s*o?\s*alaikum)\b[\s,!.]*|"
    r"(?:can|could|would|will)\s+you\s+|tell\s+me(?:\s+about)?\s+|explain\s+|describe\s+|"
    r"give\s+me\s+|show\s+me\s+|i\s+want\s+to\s+know(?:\s+about)?\s+|"
    r"(?:what|how|why|who|when|where|which)(?:'s|\s+(?:is|are|was|were|do|does|did|can|to|should))?\s+)",
    re.IGNORECASE
)
SMALL_WORDS = {"a", "an", "the", "and", "or", "of", "for", "in", "on", "to", "with", "vs", "at", "by", "from"}
# Where a quick subject is cut: "Literacy Rate in the Developed Countries" -> "Literacy Rate"
SUBJECT_BREAKS = {"in", "of", "for", "to", "with", "on", "at", "by", "from", "about", "between", "using", "and", "vs"}
SUBJECT_LEADING_WORDS = {"the", "a", "an", "and", "but", "so", "or", "in", "on", "at", "for", "about", "of"}


def fallback_title(question):
    """Turn the first question into a title, e.g. "What are COVID-19 precautions?" -> "COVID-19 Precautions\""""
    text = re.sub(r"\bplease\b", "", " ".join(str(question or "").split()), flags=re.IGNORECASE)
    text = text.strip(" ?!.,")
    for _ in range(4):  # "Hi, can you explain what ..." has several leading phrases
        text = QUESTION_START.sub("", text).strip()
    words = text.split()[:6]
    if not words:
        # Only a greeting such as "Hi": keep it rather than show nothing.
        return " ".join(str(question or "").split()).strip(" ?!.,").capitalize()[:40] or "New Chat"
    titled = []
    for index, word in enumerate(words):
        if index and word.lower() in SMALL_WORDS:
            titled.append(word.lower())
        elif word.isupper() or any(char.isdigit() for char in word):
            titled.append(word)
        else:
            titled.append(word[:1].upper() + word[1:])
    return " ".join(titled)


def fallback_subject(question):
    """A quick subject from the question itself, shown until the model's subject arrives"""
    words = fallback_title(question).split()
    # "The Literacy Rate" -> "Literacy Rate", "And in Hospitals" -> "Hospitals"
    while len(words) > 1 and words[0].lower() in SUBJECT_LEADING_WORDS:
        words = words[1:]
    for index, word in enumerate(words):
        if index and word.lower() in SUBJECT_BREAKS:
            words = words[:index]
            break
    return " ".join(words[:4])


def clean_title(raw):
    """First line of the model's answer without quotes or labels, or None if unusable"""
    line = next((line for line in str(raw or "").splitlines() if line.strip()), "")
    line = line.strip(" \"'*#.`")
    # Drop labels such as "Title:" or "Here is the heading:" that some models add.
    line = re.sub(r"^(?:here(?: is|'s) (?:the|a|your) )?(?:title|heading|subject)[^:]{0,20}:\s*", "", line, flags=re.IGNORECASE)
    line = line.strip(" \"'*#.`")
    if not line or len(line.split()) > 6:
        return None
    if len(line) > 50:
        line = line[:50].rsplit(" ", 1)[0]  # never cut a word in half
    return line


class LabelService:
    def __init__(self, db, llama, busy=lambda: False):
        self.db = db
        self.llama = llama
        # Labels wait while a chat reply is being generated, so they never slow the chat down.
        self.busy = busy
        self.jobs = queue.PriorityQueue()
        self.order = itertools.count()  # first in, first out within a priority
        self.pending = set()
        self.failed = {}
        self.lock = threading.Lock()
        threading.Thread(target=self._worker, daemon=True).start()

    def request_title(self, user_id, session_id):
        """Queue a chat session to be (re)titled"""
        self._queue(("title", user_id, session_id))

    def request_subject(self, user_id, message_id):
        """Queue a question to get its subject"""
        self._queue(("subject", user_id, message_id))

    def request_missing_subjects(self, user_id):
        """Queue the user's recent questions that have no subject yet"""
        for message_id in self.db.get_questions_without_subject(user_id, MISSING_SUBJECTS_BATCH):
            self.request_subject(user_id, message_id)

    def pending_titles(self, user_id):
        with self.lock:
            return sum(1 for kind, uid, _ in self.pending if kind == "title" and uid == user_id)

    def _queue(self, job):
        with self.lock:
            # A label that just failed is not retried at once, so failures cannot loop.
            if job in self.pending or time.time() - self.failed.get(job, 0) < RETRY_AFTER_SECONDS:
                return
            self.pending.add(job)
            self.jobs.put((PRIORITY[job[0]], next(self.order), job))

    def _worker(self):
        while True:
            _, _, job = self.jobs.get()
            while self.busy():
                time.sleep(1)
            labelled = False
            kind, user_id, target = job
            try:
                labelled = self._title(user_id, target) if kind == "title" else self._subject(user_id, target)
            except Exception as e:
                print(f"❌ Could not write the {kind} for {target}: {e}")
            finally:
                with self.lock:
                    self.pending.discard(job)
                    if not labelled:
                        self.failed[job] = time.time()
            time.sleep(PAUSE_SECONDS)

    def _title(self, user_id, session_id):
        """Write and store a chat title; True when a title was saved"""
        messages = self.db.get_messages(user_id, session_id)
        questions = [m["content"] for m in messages if m["role"] == "user"]
        if not questions:
            return False
        answer = clean_reply(next((m["content"] for m in messages if m["role"] == "bot"), ""))
        lines = [f"User: {q[:200]}" for q in questions[:MAX_QUESTIONS]]
        lines.insert(1, f"Assistant: {answer[:300]}")
        title = clean_title(self.llama.generate_label(TITLE_PROMPT.format(chat="\n".join(lines))))
        if not title:
            return False
        self.db.save_session_title(user_id, session_id, title)
        print(f"🏷️ Session {session_id} titled: {title}")
        return True

    def _subject(self, user_id, message_id):
        """Write and store the subject of one question; True when a subject was saved"""
        question, previous = self.db.get_question_context(user_id, message_id)
        if not question:
            return False
        context = f"The previous question in this chat was: \"{previous[:200]}\"\n\n" if previous else ""
        subject = clean_title(self.llama.generate_label(SUBJECT_PROMPT.format(question=question[:300], previous=context)))
        if not subject:
            return False
        self.db.save_message_subject(user_id, message_id, subject)
        print(f"🔖 Subject \"{subject}\" for: {question[:60]}")
        return True
