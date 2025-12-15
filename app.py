from flask import Flask, request, jsonify, send_from_directory, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
import requests, os
from flask_session import Session

load_dotenv()

app = Flask(__name__)
CORS(app)

# Session config (server-side)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = os.getenv("APP_SECRET_TOKEN", "defaultsecret123")
Session(app)

# Rate limit: 10 per minute per IP
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
MAX_CONTEXT = 3  # keep last 3 Q&A exchanges only

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/ask", methods=["POST"])
@limiter.limit("10 per minute")
def ask():
    try:
        data = request.get_json(force=True)
        question = data.get("question", "").strip()

        if not question:
            return jsonify({"answer": "❗ Please type a question."}), 400

        if not API_KEY:
            return jsonify({"answer": "⚠️ Server misconfiguration."}), 500

        # Initialize context if not exists
        if 'context' not in session:
            session['context'] = []

        # Append new question
        session['context'].append(f"User: {question}")

        # Keep only last MAX_CONTEXT Q&A
        # Q+A counts as 2 items
        if len(session['context']) > MAX_CONTEXT * 2:
            session['context'] = session['context'][-MAX_CONTEXT*2:]

        # Build context prompt for AI
        context_text = "\n".join(session['context'])
        prompt = f"{context_text}\nAI:"

        url = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": API_KEY}
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}]
        }

        response = requests.post(url, headers=headers, params=params, json=payload, timeout=15)
        response.raise_for_status()
        ai_data = response.json()

        candidates = ai_data.get("candidates")
        if not candidates:
            return jsonify({"answer": "⚠️ No response from AI."}), 500

        reply = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()

        # Append AI reply to context
        session['context'].append(f"AI: {reply}")
        session.modified = True

        return jsonify({"answer": reply})

    except requests.exceptions.Timeout:
        return jsonify({"answer": "⏳ AI took too long. Please retry."}), 504

    except Exception as e:
        print(e)
        return jsonify({"answer": "❌ Internal server error."}), 500