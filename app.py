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
    default_limits=["10 per minute"]
)

# -------------------- STATIC SEO FILES --------------------

@app.route("/sitemap.xml")
def sitemap():
    return send_from_directory(".", "sitemap.xml")

@app.route("/robots.txt")
def robots():
    return send_from_directory(".", "robots.txt")

# -------------------- PAGES --------------------

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/<path:page>")
def pages(page):
    return send_from_directory(".", page)

# -------------------- API KEYS --------------------
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
GROQ_KEY   = os.getenv("GROQ_API_KEY")

GEMINI_MODEL = "gemini-2.5-flash"
GROQ_MODEL   = "llama-3.1-8b-instant"

MAX_CONTEXT = 4

# -------------------- HELPERS --------------------
def get_context():
    if "context" not in session:
        session["context"] = []
    return session["context"]

def trim_context(ctx):
    return ctx[-MAX_CONTEXT*2:]

# -------------------- GEMINI --------------------
def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent"
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }]
    }
    r = requests.post(url, params={"key": GEMINI_KEY}, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

# -------------------- GROQ --------------------
def call_groq(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }
    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=15
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# -------------------- ASK --------------------
@app.route("/ask", methods=["POST"])
@limiter.limit("10 per minute")
def ask():
    try:
        data = request.get_json(force=True)
        question = data.get("question", "").strip()

        if not question:
            return jsonify({"answer": "❗ Please ask a question."}), 400

        ctx = get_context()
        ctx.append(f"User: {question}")
        ctx = trim_context(ctx)
        session["context"] = ctx

        prompt = "\n".join(ctx) + "\nAI:"

        providers = ["gemini", "groq"]
        random.shuffle(providers)

        reply = None
        for p in providers:
            try:
                if p == "gemini" and GEMINI_KEY:
                    reply = call_gemini(prompt)
                    break
                if p == "groq" and GROQ_KEY:
                    reply = call_groq(prompt)
                    break
            except:
                pass

        if not reply:
            return jsonify({"answer": "⚠️ AI services are busy. Try again later."}), 503

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