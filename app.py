from flask import Flask, request, jsonify, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
import requests, os, time

load_dotenv()

app = Flask(__name__)
CORS(app)

# -------------------- Rate limit
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)

# -------------------- API KEYS
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")

GEMINI_MODEL = "gemini-2.5-flash"
GROQ_MODEL   = "llama-3.1-8b-instant"

# -------------------- Context (safe)
USER_CONTEXT = {}
MAX_CONTEXT = 4
TTL = 900  # 15 min

# --------------------
@app.route("/")
def home():
    return send_from_directory(".", "index.html")

# --------------------
def cleanup():
    now = time.time()
    for ip in list(USER_CONTEXT.keys()):
        if now - USER_CONTEXT[ip]["ts"] > TTL:
            del USER_CONTEXT[ip]

# --------------------
def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent"
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }]
    }
    r = requests.post(
        url,
        params={"key": GEMINI_API_KEY},
        json=payload,
        timeout=15
    )

    if r.status_code != 200:
        raise Exception("Gemini failed")

    data = r.json()
    return (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )

# --------------------
def call_groq(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    r = requests.post(url, headers=headers, json=payload, timeout=15)

    if r.status_code != 200:
        raise Exception("Groq failed")

    data = r.json()
    return data["choices"][0]["message"]["content"]

# --------------------
@app.route("/ask", methods=["POST"])
@limiter.limit("10 per minute")
def ask():
    try:
        cleanup()

        data = request.get_json(force=True)
        question = data.get("question", "").strip()
        if not question:
            return jsonify({"answer": "Please ask something."}), 400

        ip = get_remote_address()
        now = time.time()

        if ip not in USER_CONTEXT:
            USER_CONTEXT[ip] = {"messages": [], "ts": now}

        USER_CONTEXT[ip]["ts"] = now
        USER_CONTEXT[ip]["messages"].append(f"User: {question}")
        USER_CONTEXT[ip]["messages"] = USER_CONTEXT[ip]["messages"][-MAX_CONTEXT:]

        prompt = "\n".join(USER_CONTEXT[ip]["messages"]) + "\nAI:"

        # -------- Try Gemini first
        try:
            reply = call_gemini(prompt)
            source = "gemini"
        except Exception:
            # -------- Fallback to Groq
            reply = call_groq(prompt)
            source = "groq"

        USER_CONTEXT[ip]["messages"].append(f"AI: {reply}")
        USER_CONTEXT[ip]["messages"] = USER_CONTEXT[ip]["messages"][-MAX_CONTEXT:]

        return jsonify({
            "answer": reply,
            "source": source
        })

    except Exception as e:
        print("SERVER ERROR:", e)
        return jsonify({
            "answer": "AI service unavailable. Please retry."
        }), 503

# --------------------
@app.route("/clear-context", methods=["POST"])
def clear_context():
    USER_CONTEXT.pop(get_remote_address(), None)
    return jsonify({"status": "cleared"})

# --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))