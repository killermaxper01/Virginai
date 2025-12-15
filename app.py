from flask import Flask, request, jsonify, session, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
import requests, os

load_dotenv()

app = Flask(__name__)
CORS(app)

# ---- Security & Session ----
app.secret_key = os.getenv("APP_SECRET_TOKEN", "change_this_secret")
app.config["SESSION_PERMANENT"] = False  # clears when browser closes

# ---- Rate Limiter (per IP) ----
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
MAX_CONTEXT = 4   # last 4 Q&A only

# -----------------------------
@app.route("/")
def home():
    return Response(INDEX_HTML, mimetype="text/html")

# -----------------------------
@app.route("/ask", methods=["POST"])
@limiter.limit("10 per minute")
def ask():
    try:
        data = request.get_json()
        question = data.get("question", "").strip()

        if not question:
            return jsonify({"answer": "❗ Please enter a question."})

        if "context" not in session:
            session["context"] = []

        # Add user message
        session["context"].append(f"User: {question}")

        # Trim context
        session["context"] = session["context"][-MAX_CONTEXT*2:]

        prompt = "\n".join(session["context"]) + "\nAI:"

        url = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent"
        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": prompt}]
            }]
        }

        response = requests.post(
            url,
            params={"key": API_KEY},
            json=payload,
            timeout=20
        )
        response.raise_for_status()

        reply = response.json()["candidates"][0]["content"]["parts"][0]["text"]

        session["context"].append(f"AI: {reply}")
        session.modified = True

        return jsonify({"answer": reply})

    except requests.exceptions.Timeout:
        return jsonify({"answer": "⏳ AI timeout. Try again."})
    except Exception as e:
        print("Error:", e)
        return jsonify({"answer": "❌ Server error. Try later."})

# -----------------------------
@app.route("/clear-session", methods=["POST"])
def clear_session():
    session.clear()
    return jsonify({"status": "cleared"})

# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))