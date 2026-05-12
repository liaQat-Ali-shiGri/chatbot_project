# 🤖 LLaMA 3 Chatbot - CS619 Project

An AI-powered conversational assistant built with LLaMA 3, Flask backend, and vanilla JavaScript frontend. This project integrates with Ollama for local LLM inference and MongoDB for persistent data storage.

## Features

- 💬 **Real-time Chat Interface** - Clean, responsive chat UI with typing indicators
- 🤖 **LLaMA 3 Integration** - Uses Ollama's API for local AI inference
- 👤 **User Authentication** - Mock login system (Phase 1) with MongoDB user tracking
- 📊 **Feedback System** - Users can rate responses (good/bad) and provide detailed feedback
- 💾 **Chat History** - Persistent storage of conversations and user feedback
- 🔐 **Session Management** - User sessions with secure authentication

## Tech Stack

### Backend
- **Framework**: Flask with CORS support
- **Database**: MongoDB Atlas
- **AI Model**: LLaMA 3 via Ollama
- **Language**: Python 3.8+

### Frontend
- **HTML5** - Semantic markup
- **CSS3** - Modern styling with gradients and animations
- **JavaScript (Vanilla)** - No frameworks, pure ES6+

## Prerequisites

Before running this project, ensure you have:

- **Python 3.8+** installed
- **Ollama** installed and running with LLaMA 3 model
  - Download from: https://ollama.ai
  - Run: `ollama pull llama3`
  - Start the service: `ollama serve`
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
FLASK_SECRET_KEY=your-secret-key-here-change-for-production
FLASK_ENV=development
```

**Important**: Never commit `.env` - it's in `.gitignore` by default.

### 5. Ensure Ollama is Running

In a separate terminal, start Ollama:

```bash
ollama serve
```

You should see: `Listening on 127.0.0.1:11434`

## Running the Project

### Start the Backend Server

From the project root directory with venv activated:

```bash
python backend/app.py
```

You'll see:
```
==================================================
🤖 CHATBOT SERVER STARTING
==================================================
✅ Connected to MongoDB Atlas
✅ LLaMA 3 model found
 * Running on http://127.0.0.1:5000
```

### Access the Frontend

Open your browser and navigate to:

```
file:///path/to/chatbot_project/frontend/index.html
```

Or serve it with a simple HTTP server:

```bash
# From the frontend directory
python -m http.server 8000
```

Then open: `http://localhost:8000`

## Project Structure

```
chatbot_project/
├── backend/
│   ├── app.py              # Flask main application
│   ├── auth.py             # Authentication & session management
│   ├── db.py               # MongoDB database operations
│   └── model_handler.py    # LLaMA 3 integration with Ollama
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
- `POST /api/login` - Mock login endpoint
  - Body: `{ "email": "user@example.com", "name": "User Name" }`
  - Response: `{ "success": true, "user": {...} }`

- `POST /api/logout` - Logout and clear session
  - Response: `{ "success": true }`

### Chat
- `POST /api/chat` - Send message and get bot response
  - Body: `{ "message": "Your message here" }`
  - Response: `{ "response": "Bot response", "message_id": "..." }`

- `GET /api/history` - Get user's chat history
  - Response: `{ "history": [...] }`

### Feedback
- `POST /api/feedback` - Save feedback on a message
  - Body: `{ "message_id": "...", "rating": "good", "correctness": "correct", "length_type": "perfect" }`
  - Response: `{ "success": true }`

### Health
- `GET /api/health` - Check server and LLaMA status
  - Response: `{ "status": "ok", "llama_available": true }`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGO_URI` | MongoDB connection string | `mongodb+srv://localhost:27017/chatbot_project` |
| `FLASK_SECRET_KEY` | Secret key for session management | `your-secret-key-here-change-this-for-production` |
| `FLASK_ENV` | Flask environment | `development` |

## Troubleshooting

### Cannot connect to Ollama
- Ensure Ollama is running: `ollama serve`
- Check if it's accessible at `http://localhost:11434`
- Try running: `ollama list` to verify LLaMA 3 is installed

### MongoDB connection failed
- Verify your `MONGO_URI` in `.env` is correct
- Check your MongoDB Atlas cluster is active
- Ensure your IP is whitelisted in MongoDB Atlas network settings

### CORS errors in browser console
- Make sure the backend is running on `http://localhost:5000`
- Frontend should be opened from file or HTTP server

### LLaMA 3 takes too long to respond
- First response may take 30-60 seconds (model loading)
- Subsequent responses are faster
- Check available system memory (model requires ~4GB RAM)

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

**Built with ❤️ using LLaMA 3, Flask, and MongoDB**
