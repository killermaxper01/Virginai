from flask import Flask, request, jsonify, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
import requests, os, time

load_dotenv()

app = Flask(__name__)
CORS(app)

# ----------------------
# Rate limit per IP
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"

# ----------------------
# In-memory context store (per IP)
USER_CONTEXT = {}
MAX_CONTEXT = 4          # last 2 Q&A
CONTEXT_TTL = 900        # 15 minutes

# ----------------------
@app.route("/")
def home():
    return send_from_directory(".", "index.html")

# ----------------------
def cleanup_context():
    now = time.time()
    for ip in list(USER_CONTEXT.keys()):
        if now - USER_CONTEXT[ip]["ts"] > CONTEXT_TTL:
            del USER_CONTEXT[ip]

# ----------------------
@app.route("/ask", methods=["POST"])
@limiter.limit("10 per minute")
def ask():
    try:
        cleanup_context()

        data = request.get_json(force=True)
        question = data.get("question", "").strip()

        if not question:
            return jsonify({"answer": "❗ Please type a question."}), 400

        if not API_KEY:
            return jsonify({"answer": "⚠️ Server misconfigured."}), 500

        ip = get_remote_address()
        now = time.time()

        # Init context
        if ip not in USER_CONTEXT:
            USER_CONTEXT[ip] = {"messages": [], "ts": now}

        USER_CONTEXT[ip]["ts"] = now

        # Add user message
        USER_CONTEXT[ip]["messages"].append(f"User: {question}")
        USER_CONTEXT[ip]["messages"] = USER_CONTEXT[ip]["messages"][-MAX_CONTEXT:]

        prompt = "\n".join(USER_CONTEXT[ip]["messages"]) + "\nAI:"

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

        # ---- Gemini quota handling
        if response.status_code == 429:
            return jsonify({
                "answer": "⚠️ Daily free quota exceeded. Try again later."
            }), 429

        if response.status_code != 200:
            return jsonify({
                "answer": "⚠️ AI service busy. Try again."
            }), 503

        data = response.json()
        reply = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        if not reply:
            return jsonify({"answer": "⚠️ Empty AI response."}), 500

        # Save AI reply
        USER_CONTEXT[ip]["messages"].append(f"AI: {reply}")
        USER_CONTEXT[ip]["messages"] = USER_CONTEXT[ip]["messages"][-MAX_CONTEXT:]

        return jsonify({"answer": reply})

    except requests.exceptions.Timeout:
        return jsonify({"answer": "⏳ AI timeout. Retry."}), 504

    except Exception as e:
        print("SERVER ERROR:", e)
        return jsonify({"answer": "❌ Internal server error."}), 500

# ----------------------
@app.route("/clear-context", methods=["POST"])
def clear_context():
    ip = get_remote_address()
    USER_CONTEXT.pop(ip, None)
    return jsonify({"status": "cleared"})

# ----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))