from flask import Flask, request, jsonify, session
from flask_cors import CORS
from model_handler import llama
from db import db
from auth import mock_login, is_logged_in, get_current_user
import uuid
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your-secret-key-here-change-this-for-production")
CORS(app)

@app.route("/api/login", methods=["POST"])
def login():
    """Mock login endpoint"""
    data = request.json
    email = data.get("email")
    name = data.get("name")
    
    if email and name:
        mock_login(email, name)
        return jsonify({"success": True, "user": {"email": email, "name": name}})
    return jsonify({"success": False, "error": "Email and name required"}), 400

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/chat", methods=["POST"])
def chat():
    """Main chat endpoint"""
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.json
    user_message = data.get("message")
    
    if not user_message:
        return jsonify({"error": "Message required"}), 400
    
    user = get_current_user()
    user_id = user['user_id']
    
    # Save user message
    user_msg_id = db.save_message(user_id, "user", user_message)
    
    # Get bot response from LLaMA 3
    bot_response = llama.generate_response(user_message)
    
    # Save bot response
    bot_msg_id = db.save_message(user_id, "bot", bot_response)
    
    return jsonify({
        "response": bot_response,
        "message_id": str(bot_msg_id)
    })

@app.route("/api/feedback", methods=["POST"])
def save_feedback():
    """Save user feedback"""
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.json
    user = get_current_user()
    
    db.save_feedback(
        user_id=user['user_id'],
        message_id=data.get("message_id"),
        rating=data.get("rating"),
        correctness=data.get("correctness"),
        length_type=data.get("length_type")
    )
    
    return jsonify({"success": True})

@app.route("/api/history", methods=["GET"])
def get_history():
    """Get chat history for current user"""
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 401
    
    user = get_current_user()
    history = db.get_chat_history(user['user_id'])
    
    # Convert ObjectId to string for JSON
    for msg in history:
        msg['_id'] = str(msg['_id'])
    
    return jsonify({"history": history})

@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "llama_available": llama.is_available})

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🤖 CHATBOT SERVER STARTING")
    print("="*50)
    print(f"📍 MongoDB: {'✅ Connected' if db else '⚠️ Using fallback'}")
    print(f"📍 LLaMA 3: {'✅ Available' if llama.is_available else '⚠️ Fallback mode'}")
    print(f"📍 Server: http://localhost:5000")
    print("="*50 + "\n")
    app.run(debug=True, port=5000)