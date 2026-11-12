============================================
LLaMA 3 Multi-Turn AI Chatbot - Phase 3
Student ID: BC200403097
Supervisor: Neelam Alam
============================================

PROJECT STRUCTURE:
==================
Multi-Turn AI Chatbot/
├── backend/
│   ├── app.py                   Flask server, routes, startup of all modules
│   ├── model_handler_ollama.py  Local LLaMA 3 through Ollama (AI_MODE=ollama)
│   ├── model_handler.py         Groq API alternative (AI_MODE=groq)
│   ├── model_base.py            Reply and label handling shared by both model handlers
│   ├── context_manager.py       Topic-aware context window
│   ├── chat_titles.py           Chat history titles (main topic of each chat)
│   ├── reply_format.py          Removes hidden model reasoning from replies
│   ├── topic_classifier.py      Topic classification (scikit-learn)
│   ├── analytics.py             Analytics metrics, tables and insights (pandas)
│   ├── charts.py                Graph generation (plotly)
│   └── db.py                    MongoDB storage
├── frontend/
│   ├── login.html               Google OAuth login page
│   ├── index.html               Chat interface + feedback panel
│   ├── analytics.html           Analytics dashboard
│   ├── style.css
│   └── script.js
├── .env.example                 Template for the .env settings file
└── requirements.txt


HOW TO RUN:
============
1. Install Python 3.11 or higher (developed and tested on Python 3.13)
2. Install required packages:
   pip install -r requirements.txt

3. Install Ollama (https://ollama.com) and download LLaMA 3:
   ollama pull llama3

4. Copy .env.example to .env and fill in your values (never commit .env to git;
   the submitted archive already includes a ready .env, so steps 4 and 5 can be skipped):
   AI_MODE=ollama                  ollama = local LLaMA 3 (the project requirement),
                                   groq = Groq API alternative (not LLaMA 3, see below)
   MONGO_URI=...                   MongoDB Atlas connection string
   GOOGLE_CLIENT_ID=...            Google OAuth client
   GOOGLE_CLIENT_SECRET=...
   FLASK_SECRET_KEY=...            any long random string; keeps users signed in on restart
   Optional (defaults shown in .env.example):
   OLLAMA_URL, OLLAMA_MODEL, OLLAMA_MAX_TOKENS, OLLAMA_HISTORY_MESSAGES,
   OLLAMA_KEEP_ALIVE, OLLAMA_TIMEOUT, FLASK_DEBUG (1 = auto-reload while developing),
   GROQ_API_KEY, GROQ_PRIMARY_MODEL, GROQ_FALLBACK_MODELS, GROQ_MAX_TOKENS,
   GROQ_HISTORY_MESSAGES

5. Set up Google OAuth:
   - Go to Google Cloud Console
   - Create OAuth 2.0 Client ID
   - Add redirect URI: http://localhost:5000/login/google/callback
   - Add the client ID and secret to .env

6. Run the application:
   cd backend
   python app.py
   The console confirms each module at startup: LLaMA 3 model loaded, MongoDB connected,
   analytics module initialized.

7. Open browser and go to:
   http://localhost:5000          (http://127.0.0.1:5000 is redirected here automatically,
                                   because Google sign-in is registered for localhost)
   Service status: http://localhost:5000/api/health

Notes:
- On a computer without a GPU, local LLaMA 3 (8B) answers in roughly 15-90 seconds.
  Replies are capped at OLLAMA_MAX_TOKENS; a reply that reaches the cap says so.
- Windows may reserve Ollama's default port 11434 (the error is "bind: An attempt was made
  to access a socket in a way forbidden by its access permissions"). Then run Ollama on a
  free port and point the app to it:
      set OLLAMA_HOST=127.0.0.1:11600
      ollama serve
  and in .env:  OLLAMA_URL=http://localhost:11600
- If the model or database cannot be reached, /api/health reports "degraded", a chat
  message shows an error instead of a reply, and nothing is stored for it.


FEATURES IMPLEMENTED (PHASE 1 - SYSTEM DEVELOPMENT):
=====================================================
✅ FR1 System Initialization: with AI_MODE=ollama, LLaMA 3 is loaded into memory at startup;
       the database connection and the analytics module (topic classifier trained) are
       initialized at the same time
✅ FR2 Frontend: Google OAuth login page, chat interface, feedback panel
✅ FR3 Backend: Flask handles authentication, sessions, message routing and storage
✅ FR4 LLaMA 3 Integration: with AI_MODE=ollama, queries are processed locally by LLaMA 3.
       (AI_MODE=groq uses Groq's hosted models, by default openai/gpt-oss-20b with
       gpt-oss-120b and qwen3.8-27b as fallbacks, which are not LLaMA 3.)
✅ FR5 Service Connectivity: /api/health reports backend, model, database and analytics status


FEATURES IMPLEMENTED (PHASE 2 - CHAT EXECUTION + DATA STORAGE):
================================================================
✅ FR6 User Authentication: Google OAuth; a user profile is created on first login and
       retrieved/updated on later logins (users collection). A failed sign-in shows a message.
✅ FR7 Session Management: unique session ID per chat; each chat keeps its own context,
       separately for every user
✅ FR8 Multi-Turn Chat: continuous conversation with several topics in one session; the
       model's context is rebuilt from the database after a server restart
✅ FR9 Response Generation: replies are generated by LLaMA 3 and displayed when ready
✅ FR10 Response Time: measured from request to response for every reply
✅ FR11 Data Storage: user message, model response, session ID, timestamp and topic label
       (indexes on user, session and time are created at startup so lookups stay fast)
✅ FR12 Mandatory Feedback: rating (1-4 stars), correctness (Correct / Partial / Incorrect)
       and length (Short / To the Point / Lengthy) are all required; pressing Submit with one
       missing highlights it. Feedback is accepted once per reply, only for the user's own replies.
✅ FR13 Input Control: input is frozen while a reply is generated and until its feedback is
       submitted. The server checks the user's latest reply in any chat, so a new chat or a
       page reload cannot skip feedback; after a reload the chat that needs feedback opens.

Chat history: chats are listed with the most recent at the top. Each chat is titled with
its main topic (for example "AGI" or "Worldwide Health Issues"), written by the chat model
in the background (never while a reply is being generated) and refreshed when the session
ends. Rated replies show their feedback as badges when a chat is reopened.

Reply display: replies are shown with their formatting (bold, lists, tables, code); the
HTML is sanitized with DOMPurify. Any hidden reasoning a model emits (<think> blocks) is
removed, including from replies stored earlier.

Context management: every turn is tagged with its topic. The context sent to the model is
the recent turns on the current topic plus the previous exchange, so an unrelated earlier
topic does not affect the reply while a follow-up such as "how does dropout help with it?"
still sees what "it" refers to. Returning to an earlier topic brings its turns back.


FEATURES IMPLEMENTED (PHASE 3 - ANALYTICS SYSTEM):
===================================================
✅ FR14 Data Retrieval: every bot reply is joined with its question, topic and feedback
✅ FR15 Topic Classification: keyword rules + TF-IDF/Logistic Regression (scikit-learn)
       into Machine Learning, Deep Learning, Healthcare AI, Power Systems, E-commerce AI
       (General for anything else); follow-ups like "give an example" keep the session topic.
       Generic wording such as "AI" does not decide the domain ("What is AI?" is General).
       Each question also gets a subject that names exactly what was asked (e.g. "Literacy
       Rate" in General, "Overfitting" in Machine Learning), written by the chat model in the
       background and shown with the domain on the dashboard.
✅ FR16 Session Segmentation: each session's replies split into Start / Middle / End by position
✅ FR17 Core Metrics: accuracy per reply, topic and phase, response time statistics,
       rating averages, length distribution
✅ FR18 Correctness Evaluation: correct / partial / incorrect counts and percentages
✅ FR19 Tables: topic vs accuracy, reply correctness, phase-wise accuracy,
       response time summary, rating distribution, length preference. Tables are
       interactive: click a column heading to sort by it.
✅ FR20 Graphs (generated with plotly): topic distribution (pie), accuracy per topic (bar),
       accuracy vs phase (line), correctness per reply (bar), response time trend (line),
       rating distribution (bar), length preference (pie)
✅ FR21 Dashboard: KPIs, key insights, Topic-Based Performance (one card per AI domain
       with accuracy, correct/partial/incorrect split, rating and response time, plus
       strongest/weakest topic), graphs, tables, session-level insights, and a scope
       selector (all sessions or one session)
✅ FR22 Session Termination: "End Session" stores the final analytics summary
       permanently in the session_summaries collection and closes the session

Metric definitions:
- Accuracy = average score over rated replies (Correct = 1, Partial = 0.5, Incorrect = 0)
- Overall correctness % = Correct replies / rated replies
- Phases = a reply's position in its session, from first (Start) to last (End); the first
  reply is always Start and the last always End


TECHNOLOGIES USED:
==================
- AI Model: LLaMA 3 (8B) running locally with Ollama; Groq API as an optional alternative
- Backend: Flask (Python)
- Frontend: HTML, CSS, JavaScript
- Database: MongoDB Atlas
- Authentication: Google OAuth 2.0
- Analytics: pandas (metrics), scikit-learn (topic classification), plotly (graphs)


CONTACT:
========
Student: Liaqat Ali
Email: bc200403097@vu.edu.pk
Supervisor: Neelam Alam
Email: neelam.alam@vu.edu.pk
