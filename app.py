from flask import Flask, request, jsonify, session, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
import requests, os, random

# -------------------- SETUP --------------------
load_dotenv()

app = Flask(__name__)
CORS(app)

app.secret_key = os.getenv("APP_SECRET_TOKEN", "change_this_secret")
app.config["SESSION_PERMANENT"] = False

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["20 per minute"]
)

# -------------------- SECURITY + CACHE HEADERS --------------------
@app.after_request
def add_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    if request.path.startswith("/ask") or request.path.startswith("/clear-session"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    else:
        response.headers["Cache-Control"] = "no-cache, must-revalidate"

    return response

# -------------------- LOAD NUMBERED API KEYS --------------------
def load_keys(prefix):
    keys = [v for k, v in os.environ.items() if k.startswith(prefix) and v.strip()]
    random.shuffle(keys)
    return keys

GEMINI_KEYS = load_keys("GEMINI_KEY_")
GROQ_KEYS   = load_keys("GROQ_KEY_")

# -------------------- MODELS --------------------
MODELS = {
    "normal": ["gemma-3-27b-it"],
    "hard": ["gemini-3-flash-preview", "gemini-2.5-flash-lite"],
    "think": ["gemini-3-flash-think"],
    "flash": ["llama-3.1-8b-instant"],
    "smart": ["gemma-3-27b-it"]
}

MAX_CONTEXT = 4

# -------------------- CONTEXT --------------------
def get_context():
    return session.setdefault("context", [])

def trim_context(ctx):
    return ctx[-MAX_CONTEXT * 2:]

# -------------------- GEMINI CALL --------------------
def call_gemini(prompt, model):
    for key in random.sample(GEMINI_KEYS, len(GEMINI_KEYS)):
        try:
            url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"
            payload = {
                "contents": [{
                    "role": "user",
                    "parts": [{"text": prompt}]
                }]
            }
            r = requests.post(url, params={"key": key}, json=payload, timeout=15)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except:
            continue
    return None

# -------------------- GROQ CALL --------------------
def call_groq(prompt):
    for key in random.sample(GROQ_KEYS, len(GROQ_KEYS)):
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=15
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except:
            continue
    return None

# -------------------- AI ROUTER --------------------
def generate_ai(prompt, mode):
    tried = set()
    queue = MODELS.get(mode, []) + ["llama-3.1-8b-instant", "gemma-3-27b-it"]

    for model in queue:
        if model in tried:
            continue
        tried.add(model)

        if "llama" in model:
            reply = call_groq(prompt)
        else:
            reply = call_gemini(prompt, model)

        if reply:
            return reply

    return None

# -------------------- ASK API --------------------
@app.route("/ask", methods=["POST"])
@limiter.limit("20 per minute")
def ask():
    try:
        data = request.get_json(force=True)
        question = data.get("question", "").strip()
        mode = data.get("mode", "normal").lower()

        if not question:
            return jsonify({"answer": "❗ Please ask a question."}), 400

        ctx = get_context()
        ctx.append(f"User: {question}")
        session["context"] = trim_context(ctx)

        prompt = "\n".join(session["context"]) + "\nAI:"

        reply = generate_ai(prompt, mode)

        if not reply:
            return jsonify({"answer": "⚠️ AI services are busy. Try again later."}), 503

        session["context"].append(f"AI: {reply}")
        session["context"] = trim_context(session["context"])
        session.modified = True

        return jsonify({"answer": reply})

    except requests.exceptions.Timeout:
        return jsonify({"answer": "⏳ AI timeout. Try again."}), 504
    except Exception as e:
        print("SERVER ERROR:", e)
        return jsonify({"answer": "❌ Server error. Please retry."}), 500

# -------------------- CLEAR SESSION --------------------
@app.route("/clear-session", methods=["POST"])
def clear_session():
    session.clear()
    return jsonify({"status": "cleared"})

# -------------------- STATIC --------------------
@app.route("/sitemap.xml")
def sitemap():
    return send_from_directory(".", "sitemap.xml")

@app.route("/robots.txt")
def robots():
    return send_from_directory(".", "robots.txt")

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/<path:path>")
def fallback(path):
    if os.path.exists(path):
        return send_from_directory(".", path)
    return send_from_directory(".", "index.html")

# -------------------- RUN --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))