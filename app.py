from flask import Flask, request, jsonify, session, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
import requests, os, random
from werkzeug.middleware.proxy_fix import ProxyFix
#new pip 
import base64, io
from PIL import Image
import PyPDF2
from flask import Response
#firebase integration 


import json
import firebase_admin
from firebase_admin import credentials, messaging

if not firebase_admin._apps:
    firebase_json = os.getenv("FIREBASE_ADMIN_JSON")
    if not firebase_json:
        raise RuntimeError("FIREBASE_ADMIN_JSON env not set")

    cred_dict = json.loads(firebase_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

# -------------------- SETUP --------------------
load_dotenv()

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)  # ✅ MUST be after app creation

CORS(app)

app.secret_key = os.getenv("APP_SECRET_TOKEN", "change_this_secret")
app.config["SESSION_PERMANENT"] = False

# -------------------- RATE LIMITER --------------------
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["30 per minute"]  # shared IP safe
)

# -------------------- SECURITY + CACHE HEADERS --------------------
@app.after_request
def add_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    # ✅ ETag NOT REMOVED
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
    "smart": ["gemma-3-27b-it"],
    "internet": ["gemini-3-flash-preview", "gemini-2.5-flash-lite"],
    "think": ["gemini-3-flash-think"],
    "flash": ["llama-3.1-8b-instant"],
}

MAX_CONTEXT = 4

# -------------------- CONTEXT --------------------
def get_context():
    return session.setdefault("context", [])

def trim_context(ctx):
    return ctx[-MAX_CONTEXT * 2:]

# -------------------- GEMINI CALL --------------------
def call_gemini(prompt, model, internet=False):
    for key in random.sample(GEMINI_KEYS, len(GEMINI_KEYS)):
        try:
            url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"

            payload = {
                "contents": [{
                    "role": "user",
                    "parts": [{"text": prompt}]
                }]
            }

            if internet:
                payload["tools"] = [{"google_search": {}}]

            r = requests.post(
                url,
                params={"key": key},
                json=payload,
                timeout=20
            )
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]

        except Exception:
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
        except Exception:
            continue
    return None

#vision model 
GEMINI_VISION_MODEL = "gemini-2.5-flash"

def call_gemini_vision(file, question):
    for key in random.sample(GEMINI_KEYS, len(GEMINI_KEYS)):
        try:
            img = Image.open(file.stream).convert("RGB")
            img = img.resize((768, 768))

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=65)
            img_b64 = base64.b64encode(buf.getvalue()).decode()

            payload = {
                "contents": [{
                    "role": "user",
                    "parts": [
                        {"text": question},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": img_b64
                            }
                        }
                    ]
                }]
            }

            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_VISION_MODEL}:generateContent",
                params={"key": key},
                json=payload,
                timeout=25
            )
            r.raise_for_status()

            return r.json()["candidates"][0]["content"]["parts"][0]["text"]

        except Exception as e:
            print("VISION ERROR:", e)
            continue

    return None

#text extract    
def extract_text_from_file(file):
    try:
        name = file.filename.lower()

        if name.endswith(".txt") or name.endswith(".py") or name.endswith(".html") or name.endswith(".css"):
            return file.read().decode("utf-8", errors="ignore"), None

        if name.endswith(".pdf"):
            reader = PyPDF2.PdfReader(file.stream)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return text[:8000], None  # context safe

        return None, "❗ Unsupported file type"

    except Exception as e:
        return None, "❌ File processing failed"    




# -------------------- AI ROUTER --------------------
def generate_ai(prompt, mode):
    """
    MODE BEHAVIOR SUMMARY:

    smart:
        → Gemini: gemma-3-27b-it
        → if fails → Groq: llama-3.1-8b-instant

    internet:
        → Gemini with Google Search tool:
            - gemini-3-flash-preview
            - gemini-2.5-flash-lite
        → if all fail → smart model
        → if still fail → Groq

    think:
        → Gemini reasoning model:
            - gemini-3-flash-think
        → if fails → smart model
        → if still fail → Groq

    flash:
        → Groq (fastest & cheapest):
            - llama-3.1-8b-instant
        → if Groq fails → smart model
    """

    # ---------- helper: try Gemini ----------
    def try_gemini(model, internet=False):
        reply = call_gemini(prompt, model, internet)
        return (reply, model) if reply else (None, None)

    # ---------- helper: try Groq ----------
    def try_groq():
        reply = call_groq(prompt)
        return (reply, "llama-3.1-8b-instant") if reply else (None, None)

    # ---------------- SMART MODE ----------------
    # Default mode for normal chat
    if mode == "smart":
        reply, model = try_gemini("gemma-3-27b-it")
        return (reply, model) if reply else try_groq()

    # ---------------- INTERNET MODE ----------------
    # Enables Google search tool inside Gemini
    if mode == "internet":
        for m in MODELS["internet"]:
            reply, model = try_gemini(m, internet=True)
            if reply:
                return reply, model

        # fallback chain: smart → groq
        reply, model = try_gemini("gemma-3-27b-it")
        return (reply, model) if reply else try_groq()

    # ---------------- THINK MODE ----------------
    # Pure reasoning, no tools
    if mode == "think":
        reply, model = try_gemini("gemini-3-flash-think")
        if reply:
            return reply, model

        reply, model = try_gemini("gemma-3-27b-it")
        return (reply, model) if reply else try_groq()

    # ---------------- FLASH MODE ----------------
    # Fastest responses (Groq)
    if mode == "flash":
        reply, model = try_groq()
        return (reply, model) if reply else try_gemini("gemma-3-27b-it")

    # ---------------- UNKNOWN MODE ----------------
    # Safety fallback
    reply, model = try_gemini("gemma-3-27b-it")
    return (reply, model) if reply else try_groq()

# -------------------- ASK API --------------------
@app.route("/ask", methods=["POST"])
@limiter.limit("30 per minute")

def ask():
    try:
        data = request.get_json(force=True)
        question = data.get("question", "").strip()
        mode = data.get("mode", "smart").lower()

        if not question:
            return jsonify({"answer": "❗ Please ask a question."}), 400

        ctx = get_context()
        ctx.append(f"User: {question}")
        session["context"] = trim_context(ctx)

        prompt = "\n".join(session["context"]) + "\nAI:"
        reply, model_used = generate_ai(prompt, mode)

        if not reply:
            return jsonify({
                "answer": "⚠️ AI services are busy. Try again later.",
                "mode_used": mode,
                "model_used": None
            }), 503

        session["context"].append(f"AI: {reply}")
        session["context"] = trim_context(session["context"])
        session.modified = True

        return jsonify({
            "answer": reply,
            "mode_used": mode,
            "model_used": model_used
        })

    except requests.exceptions.Timeout:
        return jsonify({"answer": "⏳ AI timeout. Try again."}), 504

    except Exception as e:
        print("SERVER ERROR:", e)
        return jsonify({"answer": "❌ Server error. Please retry."}), 500


@app.route("/upload", methods=["POST"])
@limiter.limit("5 per minute")
def upload():
    try:
        if "file" not in request.files:
            return jsonify({"answer": "❗ No file uploaded"}), 400

        file = request.files["file"]
        question = request.form.get("question", "Explain this")
        filename = file.filename.lower()

        # ---------- IMAGE → GEMINI VISION ----------
        if filename.endswith((".jpg", ".jpeg", ".png", ".webp")):
            answer = call_gemini_vision(file, question)

            if not answer:
                return jsonify({"answer": "⚠️ Vision model busy"}), 503

            return jsonify({
                "answer": answer,
                "model_used": "gemini-2.5-flash",
                "source": "image"
            })

        # ---------- TEXT / PDF → SMART MODE ----------
        extracted_text, error = extract_text_from_file(file)
        if error:
            return jsonify({"answer": error}), 400

        prompt = f"""
User uploaded document:
{extracted_text}

User question:
{question}
"""

        reply, model_used = generate_ai(prompt, mode="smart")

        if not reply:
            return jsonify({"answer": "⚠️ AI busy"}), 503

        return jsonify({
            "answer": reply,
            "model_used": model_used,
            "source": "file"
        })

    except Exception as e:
        print("UPLOAD ERROR:", e)
        return jsonify({"answer": "❌ Server error"}), 500



#image creation 

# -------------------- IMAGE GENERATION (SECURE PROXY) --------------------

@app.route("/generate-image", methods=["POST"])
@limiter.limit("10 per minute")
def generate_image():
    try:
        data = request.get_json(force=True)
        prompt = data.get("prompt", "").strip()

        if not prompt:
            return jsonify({"error": "Prompt required"}), 400

        r = requests.post(
            os.getenv("CF_IMAGE_WORKER_URL"),
            headers={
                "Content-Type": "application/json",
                "X-Internal-Token": os.getenv("INTERNAL_TOKEN")
            },
            json={"prompt": prompt},
            timeout=60
        )

        if r.status_code != 200:
            return jsonify({"error": "Image generation failed"}), 502

        # ✅ RETURN RAW IMAGE
        return Response(
            r.content,
            mimetype="image/png",
            headers={
                "Cache-Control": "no-store",
                "X-Image-Model": "SDXL-Cloudflare"
            }
        )

    except Exception as e:
        print("IMAGE ERROR:", e)
        return jsonify({"error": "Server error"}), 500

#firebase notification 
# -------------------- SEND PUSH NOTIFICATION --------------------
@app.route("/send-bulk-notification", methods=["POST"])
@limiter.limit("2 per minute")  # 🔒 very strict
def send_bulk_notification():
    try:
        # 🔐 1️⃣ ADMIN AUTH CHECK
        admin_token = request.headers.get("X-Admin-Token")
        if admin_token != os.getenv("ADMIN_PUSH_TOKEN"):
            return jsonify({"error": "Unauthorized"}), 401

        data = request.get_json(force=True)

        title = data.get("title", "VirginAI 🔔")
        body  = data.get("body", "New update available")

        # 2️⃣ Fetch tokens
        tokens = []
        users_ref = db.collection("users").stream()

        for doc in users_ref:
            token = doc.to_dict().get("fcmToken")
            if token:
                tokens.append(token)

        if not tokens:
            return jsonify({"error": "No users found"}), 400

        # 3️⃣ Multicast
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
                image="https://virginai.in/android-chrome-192x192.png"
            ),
            data={"url": "https://virginai.in"},
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    icon="https://virginai.in/android-chrome-192x192.png",
                    badge="https://virginai.in/android-chrome-192x192.png",
                    vibrate=[200, 100, 200]
                )
            ),
            tokens=tokens
        )

        response = messaging.send_multicast(message)

        return jsonify({
            "success": True,
            "total": len(tokens),
            "sent": response.success_count,
            "failed": response.failure_count
        })

    except Exception as e:
        print("BULK ERROR:", e)
        return jsonify({"error": "Bulk send failed"}), 500


# -------------------- CLEAR SESSION --------------------
@app.route("/clear-session", methods=["POST"])
def clear_session():
    session.clear()
    return jsonify({"status": "cleared"})

# -------------------- STATIC FILES --------------------
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