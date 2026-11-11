from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')

class ChatDatabase:
    def __init__(self):
        try:
            if not MONGO_URI or '<db_password>' in MONGO_URI:
                raise ValueError('MONGO_URI is missing the real MongoDB password')

            self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            database = self.client["chatbot_project"]
            self.users = database["users"]
            self.messages = database["messages"]
            self.feedback = database["feedback"]
            self.summaries = database["session_summaries"]
            self.sessions = database["sessions"]
            print("✅ MongoDB connected")
            self._create_indexes()
        except Exception as e:
            print(f"❌ MongoDB configuration/connection error: {e}")
            self.client = None

    def _create_indexes(self):
        """Every query filters by user; indexes keep them fast as the history grows (no-op when they exist)"""
        try:
            self.messages.create_index([("user_id", 1), ("session_id", 1), ("timestamp", 1)])
            self.messages.create_index([("user_id", 1), ("role", 1), ("timestamp", 1)])
            self.messages.create_index([("user_id", 1), ("timestamp", 1)])
            self.feedback.create_index([("user_id", 1), ("message_id", 1)])
            self.summaries.create_index([("user_id", 1), ("session_id", 1)])
            self.sessions.create_index([("user_id", 1), ("session_id", 1)])
        except Exception as e:
            print(f"⚠️ Could not create MongoDB indexes: {e}")

    def is_connected(self):
        try:
            return self.client is not None and self.client.admin.command('ping').get('ok') == 1
        except Exception:
            return False

    def save_user_profile(self, email, name, picture):
        """Create the user's profile on first login, or update it on later logins (FR6)"""
        now = datetime.now()
        self.users.update_one(
            {"email": email},
            {
                "$set": {"name": name, "picture": picture, "last_login": now},
                "$setOnInsert": {"created_at": now},
                "$inc": {"login_count": 1}
            },
            upsert=True
        )

    def save_message(self, user_id, role, content, session_id=None, response_time=None, topic_label=None, timestamp=None):
        message = {
            "user_id": user_id,
            "role": role,
            "content": content,
            "session_id": session_id,
            "timestamp": timestamp or datetime.now()  # Use local time for consistency with analytics
        }
        if response_time is not None:
            message["response_time"] = response_time
        if topic_label:
            message["topic_label"] = topic_label
        return self.messages.insert_one(message).inserted_id

    def get_user_sessions(self, user_id):
        """The user's chat sessions, most recently active first"""
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$sort": {"timestamp": 1}},
            {"$group": {
                "_id": "$session_id",
                "first_message": {"$first": "$content"},
                "last_activity": {"$last": "$timestamp"}
            }},
            {"$sort": {"last_activity": -1}}
        ]
        titles = self.get_session_titles(user_id)
        return [{
            "session_id": r["_id"],
            "first_message": r["first_message"][:200],
            "title": titles.get(r["_id"]),
            "last_activity": r["last_activity"].isoformat()
        } for r in self.messages.aggregate(pipeline) if r["_id"]]

    def save_session_title(self, user_id, session_id, title):
        self.sessions.update_one(
            {"user_id": user_id, "session_id": session_id},
            {"$set": {"title": title, "title_updated_at": datetime.now()}},
            upsert=True
        )

    def get_session_titles(self, user_id):
        """Map of session id -> generated title"""
        cursor = self.sessions.find({"user_id": user_id, "title": {"$exists": True}}, {"session_id": 1, "title": 1})
        return {doc["session_id"]: doc["title"] for doc in cursor}

    def get_session_title(self, user_id, session_id):
        doc = self.sessions.find_one({"user_id": user_id, "session_id": session_id, "title": {"$exists": True}})
        return doc["title"] if doc else None

    def get_messages(self, user_id, session_id=None):
        """All stored messages of a user (optionally one session), oldest first"""
        query = {"user_id": user_id}
        if session_id:
            query["session_id"] = session_id
        return list(self.messages.find(query).sort("timestamp", 1))

    def get_session_messages(self, user_id, session_id):
        """Messages of a session with each reply's id and the feedback given on it"""
        messages = self.get_messages(user_id, session_id)
        feedback = self.feedback_by_message(user_id, [str(msg["_id"]) for msg in messages if msg["role"] == "bot"])
        return [{
            "role": msg["role"],
            "content": msg["content"],
            "message_id": str(msg["_id"]) if msg["role"] == "bot" else None,
            "feedback": feedback.get(str(msg["_id"]))
        } for msg in messages]

    def feedback_by_message(self, user_id, message_ids=None):
        """Latest feedback (rating, correctness, length) per reply: the given replies, or all of the user's"""
        query = {"user_id": user_id}
        if message_ids is not None:
            if not message_ids:
                return {}
            query["message_id"] = {"$in": message_ids}
        cursor = self.feedback.find(
            query, {"_id": 0, "message_id": 1, "rating": 1, "correctness": 1, "length_type": 1}
        ).sort("timestamp", 1)
        # Oldest first, so the latest feedback for a reply wins.
        return {doc.pop("message_id", None): doc for doc in cursor}

    def has_feedback(self, user_id, message_id):
        return self.feedback.count_documents({"user_id": user_id, "message_id": message_id}, limit=1) > 0

    def get_latest_unrated_reply(self, user_id, session_id=None):
        """The user's latest reply (in one chat, or in any) if it still needs feedback, else None (FR12, FR13)"""
        query = {"user_id": user_id, "role": "bot"}
        if session_id:
            query["session_id"] = session_id
        reply = self.messages.find_one(query, sort=[("timestamp", -1)])
        if not reply or self.has_feedback(user_id, str(reply["_id"])):
            return None
        return {"message_id": str(reply["_id"]), "session_id": reply.get("session_id")}

    @staticmethod
    def _own_message(user_id, message_id, role):
        """Query for one of the user's own messages, or None when the id is not valid"""
        if not ObjectId.is_valid(str(message_id)):
            return None
        return {"_id": ObjectId(str(message_id)), "user_id": user_id, "role": role}

    def get_reply(self, user_id, message_id):
        """A bot reply that belongs to this user, or None"""
        query = self._own_message(user_id, message_id, "bot")
        return self.messages.find_one(query) if query else None

    # ============ QUESTION SUBJECTS ============

    def save_message_subject(self, user_id, message_id, subject):
        """Store the 1-4 word subject of one of the user's questions"""
        self.messages.update_one(self._own_message(user_id, message_id, "user"), {"$set": {"subject": subject}})

    def get_question_context(self, user_id, message_id):
        """A question and the question asked just before it in the same chat: (text, previous text or None)"""
        query = self._own_message(user_id, message_id, "user")
        question = self.messages.find_one(query) if query else None
        if not question:
            return None, None
        previous = self.messages.find_one(
            {"user_id": user_id, "session_id": question.get("session_id"), "role": "user",
             "timestamp": {"$lt": question["timestamp"]}},
            sort=[("timestamp", -1)]
        )
        return question["content"], previous["content"] if previous else None

    def get_questions_without_subject(self, user_id, limit):
        """Ids of the user's most recent questions that have no subject yet"""
        cursor = self.messages.find(
            {"user_id": user_id, "role": "user", "subject": {"$exists": False}}, {"_id": 1}
        ).sort("timestamp", -1).limit(limit)
        return [str(doc["_id"]) for doc in cursor]

    def save_feedback(self, user_id, message_id, rating, correctness, length_type, session_id=None):
        return self.feedback.insert_one({
            "user_id": user_id,
            "message_id": message_id,
            "session_id": session_id,
            "rating": rating,
            "correctness": correctness,
            "length_type": length_type,
            "timestamp": datetime.now()  # Use local time for consistency
        }).inserted_id

    # ============ SESSION SUMMARIES (FR22) ============

    def save_session_summary(self, summary):
        """Store the final analytics summary of an ended session permanently"""
        self.summaries.replace_one(
            {"user_id": summary["user_id"], "session_id": summary["session_id"]},
            summary,
            upsert=True
        )

    def get_session_summary(self, user_id, session_id):
        return self.summaries.find_one({"user_id": user_id, "session_id": session_id}, {"_id": 0})

    def get_ended_sessions(self, user_id):
        """Map of ended session id -> time it ended"""
        cursor = self.summaries.find({"user_id": user_id}, {"session_id": 1, "ended_at": 1})
        return {doc["session_id"]: doc.get("ended_at") for doc in cursor}

db = ChatDatabase()
