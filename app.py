from flask import Flask, request, jsonify, session, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
import requests, os

load_dotenv()

app = Flask(__name__)
CORS(app)

# ---------------- CONFIG ----------------
app.secret_key = os.getenv("APP_SECRET_TOKEN", "change_this_secret")
app.config["SESSION_PERMANENT"] = False

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
MAX_CONTEXT = 4  # last 3–5 Q&A summary only

# ---------------- HELPERS ----------------
def safe_gemini_call(prompt):
    """Call Gemini safely without crashing"""
    url = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent"

    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }]
    }

    try:
        r = requests.post(
            url,
            params={"key": API_KEY},
            json=payload,
            timeout=25
        )
        r.raise_for_status()
        data = r.json()

        candidates = data.get("candidates")
        if not candidates:
            return "I couldn’t generate a response. Please rephrase."

        parts = candidates[0].get("content", {}).get("parts")
        if not parts:
            return "Response was empty. Try again."

        return parts[0].get("text", "No text response.")

    except requests.exceptions.Timeout:
        return "AI is taking too long. Please try again."
    except Exception as e:
        print("Gemini Error:", e)
        return "Server is busy. Please try again shortly."

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return send_file("index.html")

@app.route("/ask", methods=["POST"])
@limiter.limit("10 per minute")
def ask():
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"answer": "Please ask a question."})

    # Initialize context
    if "context" not in session:
        session["context"] = []

    # Store user message
    session["context"].append({"role": "user", "text": question})

    # Keep last N messages
    session["context"] = session["context"][-MAX_CONTEXT*2:]

    # Build summarized prompt
    summary = ""
    for item in session["context"]:
        prefix = "User" if item["role"] == "user" else "AI"
        summary += f"{prefix}: {item['text']}\n"

    summary += "AI:"

    reply = safe_gemini_call(summary)

    # Store AI reply
    session["context"].append({"role": "ai", "text": reply})
    session.modified = True

    return jsonify({"answer": reply})

@app.route("/clear-session", methods=["POST"])
def clear_session():
    session.clear()
    return jsonify({"status": "cleared"})

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))