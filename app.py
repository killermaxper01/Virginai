from flask import Flask, request, jsonify, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
import requests, os

load_dotenv()

app = Flask(__name__)
CORS(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["10 per minute"]  # prevent abuse
)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
@limiter.limit("5 per minute")
def ask():
    data = request.get_json()
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"answer": "Please ask a question."})

    url = (
        f"https://generativelanguage.googleapis.com/v1/"
        f"models/{MODEL}:generateContent?key={API_KEY}"
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": question}]
            }
        ]
    }

    try:
        r = requests.post(url, json=payload, timeout=20)
        reply = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return jsonify({"answer": reply})

    except Exception:
        return jsonify({"answer": "Server error. Please try later."})

if __name__ == "__main__":
    app.run()
