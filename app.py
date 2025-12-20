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

# -------------------- STATIC SEO FILES --------------------
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

# -------------------- API KEYS (MULTI KEY SUPPORT) --------------------
GEMINI_KEYS = [
    os.getenv("GEMINI_KEY_1"),
    os.getenv("GEMINI_KEY_2"),
    os.getenv("GEMINI_KEY_3"),
    os.getenv("GEMINI_KEY_4"),
    os.getenv("GEMINI_KEY_5"),
]

GROQ_KEYS = [
    os.getenv("GROQ_KEY_1"),
    os.getenv("GROQ_KEY_2"),
]

GEMINI_KEYS = [k for k in GEMINI_KEYS if k]
GROQ_KEYS   = [k for k in GROQ_KEYS if k]

GROQ_MODEL = "llama-3.1-8b-instant"
MAX_CONTEXT = 4

# -------------------- CONTEXT --------------------
def get_context():
    return session.setdefault("context", [])

def trim_context(ctx):
    return ctx[-MAX_CONTEXT * 2:]

# -------------------- GEMINI CORE CALL --------------------
def call_gemini_model(prompt, model):
    api_key = random.choice(GEMINI_KEYS)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}]
    }
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

# -------------------- GEMINI MODES --------------------
def gemini_normal(prompt):
    return call_gemini_model(prompt, "gemma-3-27b-it")

def gemini_hard(prompt):
    models = ["gemini-3-flash-preview", "gemini-2.5-flash-lite"]
    for m in random.sample(models, len(models)):
        try:
            return call_gemini_model(prompt, m)
        except:
            continue
    raise Exception("Hard mode failed")

def gemini_think(prompt):
    return call_gemini_model(prompt, "gemini-3-flash-think")

# -------------------- GROQ (FLASH MODE) --------------------
def call_groq(prompt):
    api_key = random.choice(GROQ_KEYS)
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }
    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=15
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

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
        ctx = trim_context(ctx)
        session["context"] = ctx

        prompt = "\n".join(ctx) + "\nAI:"

        try:
            if mode in ["normal", "smart"]:
                reply = gemini_normal(prompt)
            elif mode == "hard":
                reply = gemini_hard(prompt)
            elif mode == "think":
                reply = gemini_think(prompt)
            elif mode == "flash":
                reply = call_groq(prompt)
            else:
                reply = gemini_normal(prompt)

        except:
            # fallback → flash
            reply = call_groq(prompt)

        ctx.append(f"AI: {reply}")
        session["context"] = trim_context(ctx)
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

# -------------------- RUN --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))