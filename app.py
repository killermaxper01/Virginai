from flask import Flask, request, jsonify, session, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
import requests, os, traceback

# ------------------ Load ENV ------------------
load_dotenv()

# ------------------ App Setup -----------------
app = Flask(__name__)
CORS(app)

app.secret_key = os.getenv("APP_SECRET_TOKEN", "CHANGE_ME_NOW")
app.config["SESSION_PERMANENT"] = False  # auto clear on browser close

# ------------------ Rate Limiting -------------
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)

# ------------------ Gemini Config -------------
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
MAX_CONTEXT = 3   # last 3 Q&A only

# ------------------ Helpers -------------------
def build_contents(context, question):
    """
    Build Gemini-compatible multi-turn context
    """
    contents = []
    for q, a in context:
        contents.append({
            "role": "user",
            "parts": [{"text": q}]
        })
        contents.append({
            "role": "model",
            "parts": [{"text": a}]
        })

    contents.append({
        "role": "user",
        "parts": [{"text": question}]
    })
    return contents


# ------------------ Routes --------------------
@app.route("/")
def home():
    return send_file("index.html")


@app.route("/ask", methods=["POST"])
@limiter.limit("10 per minute")
def ask():
    try:
        # ---- Parse input safely ----
        data = request.get_json(silent=True) or {}
        question = data.get("question", "").strip()

        if not question:
            return jsonify({"answer": "Please ask something."})

        # ---- Load session context ----
        context = session.get("context", [])

        # ---- Build Gemini payload ----
        payload = {
            "contents": build_contents(context, question)
        }

        url = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent"

        # ---- Call Gemini API ----
        response = requests.post(
            url,
            params={"key": API_KEY},
            json=payload,
            timeout=25
        )

        response.raise_for_status()
        data = response.json()

        # ---- Defensive parsing ----
        candidates = data.get("candidates")
        if not candidates:
            return jsonify({"answer": "AI is busy. Please try again."})

        content = candidates[0].get("content", {})
        parts = content.get("parts")
        if not parts:
            return jsonify({"answer": "Incomplete AI response. Retry."})

        answer = parts[0].get("text", "").strip()
        if not answer:
            return jsonify({"answer": "Empty response received. Try again."})

        # ---- Save limited context ----
        context.append((question, answer))
        session["context"] = context[-MAX_CONTEXT:]

        return jsonify({"answer": answer})

    except requests.exceptions.Timeout:
        return jsonify({"answer": "AI timeout. Please retry."})

    except requests.exceptions.HTTPError as e:
        print("HTTP ERROR:", e)
        return jsonify({"answer": "AI service error. Try again shortly."})

    except Exception:
        print("SERVER ERROR:")
        traceback.print_exc()
        return jsonify({"answer": "Server busy. Please try again shortly."})


@app.route("/clear-session", methods=["POST"])
def clear_session():
    session.clear()
    return jsonify({"status": "cleared"})


# ------------------ Run -----------------------
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=False
    )