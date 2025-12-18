from flask import Flask, request, jsonify, session, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from flask_compress import Compress
from dotenv import load_dotenv
import requests, os, random

# -------------------- SETUP --------------------
load_dotenv()
app = Flask(__name__)

# CORS
CORS(app, supports_credentials=True)

# Compression (Gzip + Brotli)
Compress(app)

# Session
app.secret_key = os.getenv("APP_SECRET_TOKEN", "change_me")
app.config["SESSION_PERMANENT"] = False

# Rate limit
limiter = Limiter(get_remote_address, app=app, default_limits=["10 per minute"])

# -------------------- SECURITY HEADERS --------------------
@app.after_request
def security_headers(res):
    res.headers["X-Content-Type-Options"] = "nosniff"
    res.headers["X-Frame-Options"] = "DENY"
    res.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    res.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

    # STRICT CSP (frontend + API safe)
    res.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    # ❌ NO CACHE ANYWHERE
    res.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    res.headers["Pragma"] = "no-cache"
    res.headers["Expires"] = "0"

    return res

# -------------------- STATIC FILES (ETag ON) --------------------
@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/<path:path>")
def assets(path):
    return send_from_directory(".", path)

# -------------------- AI CONFIG --------------------
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")

GEMINI_MODEL = "gemini-2.5-flash"
GROQ_MODEL = "llama-3.1-8b-instant"
MAX_CONTEXT = 4

def get_ctx():
    return session.setdefault("ctx", [])

def trim(ctx):
    return ctx[-MAX_CONTEXT * 2:]

# -------------------- AI CALLS --------------------
def call_gemini(prompt):
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent",
        params={"key": GEMINI_KEY},
        json={"contents":[{"role":"user","parts":[{"text":prompt}]}]},
        timeout=15
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def call_groq(prompt):
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_KEY}"},
        json={"model": GROQ_MODEL, "messages":[{"role":"user","content":prompt}]},
        timeout=15
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# -------------------- ASK --------------------
@app.route("/ask", methods=["POST"])
@limiter.limit("10/minute")
def ask():
    data = request.get_json(silent=True) or {}
    q = data.get("question", "").strip()
    if not q:
        return jsonify(answer="Please ask something."), 400

    ctx = get_ctx()
    ctx.append(f"User: {q}")
    session["ctx"] = trim(ctx)

    prompt = "\n".join(session["ctx"]) + "\nAI:"
    providers = ["gemini", "groq"]
    random.shuffle(providers)

    for p in providers:
        try:
            if p == "gemini" and GEMINI_KEY:
                ans = call_gemini(prompt)
                break
            if p == "groq" and GROQ_KEY:
                ans = call_groq(prompt)
                break
        except:
            continue
    else:
        return jsonify(answer="AI busy. Try again."), 503

    ctx.append(f"AI: {ans}")
    session["ctx"] = trim(ctx)
    return jsonify(answer=ans)

# -------------------- RUN --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))