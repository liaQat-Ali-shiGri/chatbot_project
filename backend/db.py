from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
import os

# Get MongoDB connection string from environment variable
# Set this in your .env file or system environment
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://localhost:27017/chatbot_project"  # Fallback for local development
)

class ChatDatabase:
    def __init__(self):
        try:
            self.client = MongoClient(MONGO_URI)
            self.client.admin.command('ping')
            self.db = self.client["chatbot_project"]
            self.messages = self.db["messages"]
            self.feedback = self.db["feedback"]
            self.sessions = self.db["sessions"]
            print("✅ Connected to MongoDB Atlas")
        except Exception as e:
            print(f"❌ MongoDB error: {e}")
            self.use_file_fallback = True
    
    def save_message(self, user_id, role, content, session_id=None):
        doc = {
            "user_id": user_id,
            "role": role,
            "content": content,
            "session_id": session_id,
            "timestamp": datetime.utcnow()
        }
        result = self.messages.insert_one(doc)
        return result.inserted_id
    
    def get_chat_history(self, user_id, limit=50):
        cursor = self.messages.find(
            {"user_id": user_id}
        ).sort("timestamp", -1).limit(limit)
        return list(cursor)
    
    def save_feedback(self, user_id, message_id, rating, correctness, length_type):
        doc = {
            "user_id": user_id,
            "message_id": str(message_id),
            "rating": rating,
            "correctness": correctness,
            "length_type": length_type,
            "timestamp": datetime.utcnow()
        }
        return self.feedback.insert_one(doc)
    
    def create_session(self, user_id):
        doc = {
            "user_id": user_id,
            "start_time": datetime.utcnow(),
            "end_time": None,
            "message_count": 0
        }
        result = self.sessions.insert_one(doc)
        return result.inserted_id

db = ChatDatabase()