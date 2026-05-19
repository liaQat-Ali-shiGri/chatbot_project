# 🤖 LLaMA Chatbot - CS619 Project

An AI-powered conversational assistant built with Groq API, Flask backend, and vanilla JavaScript frontend. This project integrates with Groq's multi-model API for intelligent LLM inference and MongoDB Atlas for persistent data storage.

## Features

- 💬 **Real-time Chat Interface** - Clean, responsive chat UI with typing indicators
- 🤖 **Multi-Model LLM Integration** - Uses Groq API with intelligent model fallback (LLaMA 3.3 70B, LLaMA 3.1 8B, Mixtral 8x7b)
- 👤 **User Authentication** - Session-based login with MongoDB user tracking
- 📊 **Feedback System** - Users can rate responses with correctness and length preferences
- 💾 **Chat History** - Persistent storage of conversations, sessions, and user feedback
- 🔐 **Session Management** - Multiple conversation sessions per user with persistent storage
- ⚡ **Response Caching** - Intelligent caching for improved performance
- 🔄 **Smart Model Switching** - Automatic fallback to secondary models when rate limits approached

## Tech Stack

### Backend
- **Framework**: Flask 2.3.0 with CORS support
- **Database**: MongoDB Atlas
- **LLM API**: Groq API with multiple model support
- **Models Available**:
  - LLaMA 3.3 70B Versatile (Primary)
  - LLaMA 3.1 8B Instant (Fast Fallback)
  - Mixtral 8x7b 32k (Final Fallback)
- **Language**: Python 3.8+

### Frontend
- **HTML5** - Semantic markup
- **CSS3** - Modern styling with gradients and animations
- **JavaScript (Vanilla)** - No frameworks, pure ES6+
- **Icons**: Font Awesome 6.0

## Prerequisites

Before running this project, ensure you have:

- **Python 3.8+** installed
- **Groq API Key** - Get it from: https://console.groq.com
- **MongoDB Atlas** account with connection string
- **Git** for version control

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/liaQat-Ali-shiGri/chatbot_project.git
cd chatbot_project
```

### 2. Set Up Python Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?appName=Cluster
GROQ_API_KEY=your-groq-api-key-from-console.groq.com
FLASK_SECRET_KEY=your-secret-key-here-change-for-production
FLASK_ENV=development
```

**Important**: Never commit `.env` or `.env.example` containing real keys - they should be in `.gitignore` by default.

## Running the Project

### Start the Backend Server

From the project root directory with venv activated:

```bash
python backend/app.py
```

You'll see:
```
✅ MongoDB connected
Chatbot Server Running on http://localhost:5000
Initializing Multi-Model Handler with Groq API...
🟢 Active: llama-3.3-70b-versatile (30 left)
```

### Access the Frontend

Open your browser and navigate to:

```
http://localhost:5000
```

The Flask app serves the frontend automatically on the home route.

## Project Structure

```
chatbot_project/
├── backend/
│   ├── app.py              # Flask main application & API endpoints
│   ├── auth.py             # Authentication decorators
│   ├── db.py               # MongoDB database operations & queries
│   └── model_handler.py    # Groq API integration with multi-model support
├── frontend/
│   ├── index.html          # Main HTML interface
│   ├── script.js           # Chat logic & API calls
│   └── style.css           # Styling and animations
├── .env.example            # Environment variables template
├── .gitignore              # Git ignore rules
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## API Endpoints

### Authentication
- `POST /api/login` - User login with email and name
  - Body: `{ "email": "user@example.com", "name": "User Name" }`
  - Response: `{ "success": true, "user": { "email": "...", "name": "..." } }`

- `POST /api/logout` - Logout and clear session
  - Response: `{ "success": true }`

### Chat
- `POST /api/chat` - Send message and get AI response
  - Body: `{ "message": "Your message here", "session_id": "optional-session-id" }`
  - Response: `{ "response": "AI response", "message_id": "..." }`

- `GET /api/history/sessions` - Get all chat sessions for logged-in user
  - Response: `{ "sessions": { "session_id": { "first_message": "...", "timestamp": "..." } } }`

- `GET /api/history/<session_id>` - Get all messages from a specific session
  - Response: `{ "messages": [{ "role": "user|bot", "content": "..." }] }`

- `POST /api/session/switch` - Switch to a different conversation session
  - Body: `{ "session_id": "..." }`
  - Response: `{ "success": true }`

### Feedback
- `POST /api/feedback` - Submit feedback on a bot response
  - Body: `{ "message_id": "...", "rating": "good|bad", "correctness": "correct|incorrect|partial", "length_type": "too_short|perfect|too_long" }`
  - Response: `{ "success": true }`

### Health
- `GET /api/health` - Check server and active model status
  - Response: `{ "status": "ok", "active_model": "llama-3.3-70b-versatile" }`

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MONGO_URI` | MongoDB Atlas connection string | `mongodb+srv://user:pass@cluster.mongodb.net/...` |
| `GROQ_API_KEY` | Groq API key from console.groq.com | `gsk_...` |
| `FLASK_SECRET_KEY` | Secret key for session encryption | `your-secret-key-change-for-production` |
| `FLASK_ENV` | Flask environment mode | `development` or `production` |

## Troubleshooting

### Groq API errors
- Verify your `GROQ_API_KEY` in `.env` is correct
- Check if your API key is active on https://console.groq.com
- If rate limits are hit, the system will automatically fallback to the next available model

### MongoDB connection failed
- Verify your `MONGO_URI` in `.env` is correct
- Check your MongoDB Atlas cluster is active and running
- Ensure your IP address is whitelisted in MongoDB Atlas network settings

### Server fails to start
- Make sure all dependencies are installed: `pip install -r requirements.txt`
- Check if port 5000 is already in use
- Verify `.env` file exists in the project root with all required variables

### CORS or API errors in browser console
- Make sure the backend is running on `http://localhost:5000`
- Check browser console for specific error messages
- Try clearing browser cache and cookies

### Chat not responding
- Check that Groq API key is valid
- Verify MongoDB connection is working
- Check the terminal output for error messages
- Ensure you are logged in before sending messages

## Phase 2 Roadmap

- [ ] Real Google OAuth authentication
- [ ] User profiles and settings
- [ ] Chat session management
- [ ] Advanced feedback analytics
- [ ] Message search and filtering
- [ ] Export conversation history
- [ ] Multi-language support

## Security Notes

⚠️ **Important Security Considerations**:
1. Never commit `.env` file with credentials
2. Change `FLASK_SECRET_KEY` in production
3. Set up MongoDB Atlas IP whitelist
4. Use HTTPS in production (not localhost)
5. Implement rate limiting for production
6. Add input validation and sanitization

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is part of CS619 course. All rights reserved.

## Contact & Support

For issues or questions, please open an issue on GitHub.

---

**Built with ❤️ using Groq API, LLaMA Models, Flask, and MongoDB**
