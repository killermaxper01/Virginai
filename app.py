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

# -------------------- HOME --------------------
@app.route("/")
def home():
    return send_from_directory(".", "index.html")

# -------------------- FALLBACK --------------------
@app.route("/<path:path>")
def fallback(path):
    if os.path.exists(path):
        return send_from_directory(".", path)
    return send_from_directory(".", "index.html")

# -------------------- API KEYS --------------------
GEMINI_KEYS = [k.strip() for k in os.getenv("GEMINI_KEYS", "").split(",") if k.strip()]
GROQ_KEYS   = [k.strip() for k in os.getenv("GROQ_KEYS", "").split(",") if k.strip()]

# -------------------- MODELS --------------------
GEMINI_MODELS = {
    "normal": "gemma-3-27b-it",
    "hard":   "gemini-3-flash-preview",
    "think":  "gemini-3-flash-think",
    "lite":   "gemini-2.5-flash-lite",
}

GROQ_MODEL = "llama-3.1-8b-instant"
MAX_CONTEXT = 4

# -------------------- CONTEXT --------------------
def get_context():
    if "context" not in session:
        session["context"] = []
    return session["context"]

def trim_context(ctx):
    return ctx[-MAX_CONTEXT * 2:]

# -------------------- KEY FAILOVER HANDLER --------------------
def try_with_keys(call_fn, keys):
    keys = keys[:]
    random.shuffle(keys)
    last_error = None

    for key in keys:
        try:
            return call_fn(key)
        except Exception as e:
            last_error = e
            continue

    raise last_error

# -------------------- GEMINI --------------------
def call_gemini(prompt, mode="normal"):
    model = GEMINI_MODELS.get(mode, GEMINI_MODELS["normal"])

    def _call(api_key):
        url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"
        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": prompt}]
            }]
        }
        r = requests.post(
            url,
            params={"key": api_key},
            json=payload,
            timeout=15
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    return try_with_keys(_call, GEMINI_KEYS)

# -------------------- GROQ (FLASH) --------------------
def call_groq(prompt):
    def _call(api_key):
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=15
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    return try_with_keys(_call, GROQ_KEYS)

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
            reply = call_gemini(prompt, mode)
        except Exception:
            reply = call_groq(prompt)  # HARD FAILOVER

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