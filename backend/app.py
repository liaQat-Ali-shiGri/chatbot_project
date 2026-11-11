from flask import Flask, request, jsonify, session, send_file, redirect, url_for
from authlib.integrations.flask_client import OAuth
from functools import wraps
import os
import threading
from datetime import datetime
import secrets
from dotenv import load_dotenv

load_dotenv()

# Choose AI handler based on environment
AI_MODE = os.getenv('AI_MODE', 'ollama').lower()  # ollama or groq

if AI_MODE == 'ollama':
    from model_handler_ollama import llama
    print("🦙 OLLAMA MODE: Using local LLaMA 3")
elif AI_MODE == 'groq':
    from model_handler import llama
    print("🚀 GROQ MODE: Using Groq API")
else:
    raise ValueError(f"AI_MODE must be 'ollama' or 'groq', not '{AI_MODE}'")

from db import db
from topic_classifier import classifier, GENERAL
from analytics import AnalyticsEngine, CORRECTNESS, LENGTH_TYPES, RATINGS
from chat_titles import LabelService, fallback_title
from reply_format import clean_reply, NO_ANSWER_NOTE

analytics = AnalyticsEngine(db)
print("✅ Analytics module initialized (topic classifier trained)")

# Users whose reply is being generated right now: one reply at a time per user (FR13).
generating = set()
generating_lock = threading.Lock()
# Chat titles and question subjects are written in the background, never during a reply.
labels = LabelService(db, llama, busy=lambda: bool(generating))

app = Flask(__name__)
# A fixed key from .env keeps users signed in when the server restarts.
app.secret_key = os.getenv('FLASK_SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    access_token_url='https://oauth2.googleapis.com/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={
        'scope': 'openid email profile',
        'prompt': 'select_account'
    },
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    authorize_state=None,
)

frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend')


def login_required(view):
    """API routes answer 401 until the user has signed in with Google"""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Not logged in"}), 401
        return view(*args, **kwargs)
    return wrapper


@app.before_request
def use_localhost():
    # Google sign-in is registered for localhost and cookies are kept per host, so 127.0.0.1 is redirected.
    if request.method == "GET" and request.host.startswith("127.0.0.1"):
        return redirect(request.url.replace("127.0.0.1", "localhost", 1))


@app.route('/')
def index():
    page = 'index.html' if 'user_id' in session else 'login.html'
    return send_file(os.path.join(frontend_path, page))

@app.route('/script.js')
def script():
    return send_file(os.path.join(frontend_path, 'script.js'))

@app.route('/style.css')
def style():
    return send_file(os.path.join(frontend_path, 'style.css'))

@app.route('/analytics')
def analytics_page():
    if 'user_id' not in session:
        return redirect('/')
    return send_file(os.path.join(frontend_path, 'analytics.html'))

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/login/google/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
        userinfo_endpoint = 'https://www.googleapis.com/oauth2/v3/userinfo'
        resp = google.get(userinfo_endpoint, token=token)
        user_info = resp.json()

        if not user_info.get('email'):
            raise Exception("No email received from Google")

        name = user_info.get('name', user_info['email'])
        db.save_user_profile(user_info['email'], name, user_info.get('picture', ''))

        session.permanent = True
        session['user_id'] = user_info['email']
        session['user_name'] = name

        print(f"✅ User logged in: {user_info['email']}")

        return redirect('/')
    except Exception as e:
        print(f"❌ OAuth error: {e}")
        return redirect('/?login_error=1')

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/user", methods=["GET"])
@login_required
def get_user():
    return jsonify({"name": session['user_name'], "email": session['user_id']})


def stored_turns(user_id, session_id):
    """Earlier turns of a chat from the database, so the model keeps its context after a restart"""
    turns = []
    for message in db.get_messages(user_id, session_id):
        is_user = message["role"] == "user"
        content = message["content"] if is_user else clean_reply(message["content"])
        if content:
            turns.append({"role": "user" if is_user else "assistant", "content": content,
                          "topic": message.get("topic_label") or GENERAL})
    return turns


@app.route("/api/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    session_id = data.get("session_id")
    if not user_message or not session_id:
        return jsonify({"error": "Message and session id required"}), 400

    user_id = session['user_id']
    # The latest reply in any chat must be rated first, so a new chat or a page reload cannot skip feedback.
    if db.get_latest_unrated_reply(user_id):
        return jsonify({"error": "Please submit feedback for your last reply before sending another message"}), 409
    if db.get_session_summary(user_id, session_id):
        return jsonify({"error": "This session has ended. Start a new chat to continue."}), 409

    with generating_lock:
        if user_id in generating:
            return jsonify({"error": "Please wait for the current reply to finish"}), 409
        generating.add(user_id)
    try:
        request_started = datetime.now()
        # The model's context is kept per user and chat, and rebuilt from the database when missing.
        context_key = f"{user_id}|{session_id}"
        if not llama.context.has(context_key):
            llama.context.load(context_key, stored_turns(user_id, session_id))
        # A follow-up such as "give an example" keeps the topic of the chat's previous turn.
        topic_label = classifier.classify(user_message, previous_topic=llama.context.last_topic(context_key))
        bot_response = llama.generate_response(user_message, session_id=context_key, topic=topic_label)
        if not bot_response:
            # Nothing is stored, so a failed reply never needs feedback or skews the analytics.
            return jsonify({"error": "The AI model did not respond. Please try again in a moment."}), 503

        response_time = round((datetime.now() - request_started).total_seconds(), 3)
        question_id = db.save_message(user_id, "user", user_message, session_id, topic_label=topic_label, timestamp=request_started)
        msg_id = db.save_message(user_id, "bot", bot_response, session_id, response_time, topic_label)
        labels.request_subject(user_id, str(question_id))
        return jsonify({"response": bot_response, "message_id": str(msg_id), "topic": topic_label})
    except Exception:
        app.logger.exception("Chat request failed")
        return jsonify({"error": "Chat request failed. Please try again."}), 500
    finally:
        with generating_lock:
            generating.discard(user_id)

@app.route("/api/feedback", methods=["POST"])
@login_required
def feedback():
    data = request.get_json(silent=True) or {}
    user_id = session['user_id']

    rating = data.get("rating")
    if rating not in RATINGS and rating not in RATINGS.values():
        return jsonify({"error": "Rating must be between 1 and 4"}), 400
    if data.get("correctness") not in CORRECTNESS:
        return jsonify({"error": f"Correctness must be one of: {', '.join(CORRECTNESS)}"}), 400
    if data.get("length_type") not in LENGTH_TYPES:
        return jsonify({"error": f"Length type must be one of: {', '.join(LENGTH_TYPES)}"}), 400

    # Feedback is accepted once, and only for one of this user's own replies.
    reply = db.get_reply(user_id, data.get("message_id"))
    if not reply:
        return jsonify({"error": "Reply not found"}), 404
    if db.has_feedback(user_id, str(reply["_id"])):
        return jsonify({"error": "This reply already has feedback"}), 409

    db.save_feedback(
        user_id=user_id,
        message_id=str(reply["_id"]),
        rating=int(rating),
        correctness=data.get("correctness"),
        length_type=data.get("length_type"),
        session_id=reply.get("session_id")
    )

    return jsonify({"success": True})

@app.route("/api/health", methods=["GET"])
def health():
    """FR5: connectivity of every service the chatbot depends on"""
    services = {
        "backend": True,
        "model": llama.ready,
        "database": db.is_connected(),
        "analytics": True  # built at startup; the server does not start without it
    }
    return jsonify({
        "status": "ok" if all(services.values()) else "degraded",
        "services": services,
        "ai_mode": AI_MODE,
        "active_model": llama.active_model
    })

@app.route("/api/history/sessions", methods=["GET"])
@login_required
def get_sessions():
    user_id = session['user_id']
    sessions_data = db.get_user_sessions(user_id)  # most recently active first
    ended_sessions = db.get_ended_sessions(user_id)
    for info in sessions_data:
        info["ended"] = info["session_id"] in ended_sessions
        if not info["title"]:
            # Chats get a generated title in the background; until then the question is shown.
            labels.request_title(user_id, info["session_id"])
            info["title"] = fallback_title(info["first_message"])

    return jsonify({
        "sessions": sessions_data,
        "titles_pending": labels.pending_titles(user_id),
        # The reply still waiting for feedback, so the page can open that chat first.
        "pending_feedback": db.get_latest_unrated_reply(user_id)
    })

@app.route("/api/history/<session_id>", methods=["GET"])
@login_required
def get_session_messages(session_id):
    user_id = session['user_id']
    messages = db.get_session_messages(user_id, session_id)
    for message in messages:
        if message["role"] == "bot":
            # Replies stored before reasoning was stripped are cleaned for display.
            message["content"] = clean_reply(message["content"]) or NO_ANSWER_NOTE

    return jsonify({"messages": messages, "ended": db.get_session_summary(user_id, session_id) is not None})

@app.route("/api/session/end", methods=["POST"])
@login_required
def end_session():
    """FR22: end a session and store its final analytics summary permanently"""
    user_id = session['user_id']
    session_id = (request.get_json(silent=True) or {}).get("session_id")
    if not session_id:
        return jsonify({"error": "Session id required"}), 400

    if user_id in generating:
        return jsonify({"error": "Please wait for the current reply to finish"}), 409
    if db.get_latest_unrated_reply(user_id, session_id):
        return jsonify({"error": "Please submit feedback for the last reply before ending the session"}), 409
    if db.get_session_summary(user_id, session_id):
        return jsonify({"error": "This session has already ended"}), 409

    summary = analytics.build_session_summary(user_id, session_id)
    if not summary:
        return jsonify({"error": "This session has no messages yet"}), 400
    db.save_session_summary(dict(summary))

    # The session is finished, so its conversation context is no longer needed.
    llama.context.clear(f"{user_id}|{session_id}")
    labels.request_title(user_id, session_id)  # re-title from the whole conversation

    summary["started_at"] = summary["started_at"].isoformat()
    summary["ended_at"] = summary["ended_at"].isoformat()
    return jsonify({"success": True, "summary": summary})

# ============ ANALYTICS ROUTES ============

@app.route("/api/analytics/dashboard", methods=["GET"])
@login_required
def get_analytics_dashboard():
    """FR14-FR21: metrics, tables, chart data and insights for all sessions or one session"""
    session_id = request.args.get('session_id') or None
    theme = "dark" if request.args.get('theme') == "dark" else "light"
    labels.request_missing_subjects(session['user_id'])
    return jsonify(analytics.build_dashboard(session['user_id'], session_id, theme))

if __name__ == '__main__':
    print("🌐 Open http://localhost:5000 in your browser")
    # FLASK_DEBUG=1 in .env turns on auto-reload and the debugger while developing.
    app.run(host='127.0.0.1', port=5000, debug=os.getenv('FLASK_DEBUG') == '1')
