from flask import Flask, request, jsonify, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
import requests, os

load_dotenv()

app = Flask(__name__)
CORS(app)

# Rate limit: SAME IP → 10 per minute
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/ask", methods=["POST"])
@limiter.limit("10 per minute")
def ask():
    try:
        # Force JSON parsing (prevents silent failures)
        data = request.get_json(force=True)
        question = data.get("question", "").strip()

        if not question:
            return jsonify({"answer": "❗ Question cannot be empty."}), 400

        if not API_KEY:
            return jsonify({"answer": "⚠️ Server misconfiguration."}), 500

        url = (
            f"https://generativelanguage.googleapis.com/v1/"
            f"models/{MODEL}:generateContent"
        )

        headers = {
            "Content-Type": "application/json"
        }

        params = {
            "key": API_KEY
        }

        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": question}]
            }]
        }

        response = requests.post(
            url,
            headers=headers,
            params=params,
            json=payload,
            timeout=15
        )

        # Gemini API error handling
        if response.status_code != 200:
            return jsonify({
                "answer": "⚠️ AI service is busy. Try again later."
            }), 503

        data = response.json()

        # Safe parsing
        candidates = data.get("candidates")
        if not candidates:
            return jsonify({
                "answer": "⚠️ No response from AI."
            }), 500

        reply = (
            candidates[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        if not reply:
            return jsonify({
                "answer": "⚠️ Empty response from AI."
            }), 500

        return jsonify({"answer": reply})

    except requests.exceptions.Timeout:
        return jsonify({
            "answer": "⏳ AI took too long. Please retry."
        }), 504

    except Exception:
        return jsonify({
            "answer": "❌ Internal server error."
        }), 500