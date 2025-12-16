from flask import Flask, request, jsonify, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
import requests, os, traceback

# ------------------ Setup ------------------
load_dotenv()

app = Flask(__name__)
CORS(app)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"

# ------------------ Routes ------------------
@app.route("/")
def home():
    return send_file("index.html")


@app.route("/ask", methods=["POST"])
@limiter.limit("10 per minute")
def ask():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"answer": "Invalid request."})

        question = data.get("question", "").strip()
        if not question:
            return jsonify({"answer": "Please enter a question."})

        url = (
            f"https://generativelanguage.googleapis.com/v1/"
            f"models/{MODEL}:generateContent"
        )

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": question}]
                }
            ]
        }

        response = requests.post(
            url,
            params={"key": API_KEY},
            json=payload,
            timeout=25
        )

        response.raise_for_status()
        data = response.json()

        # ---- Safe extraction ----
        answer = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        if not answer:
            return jsonify({"answer": "No response from AI. Try again."})

        return jsonify({"answer": answer})

    except requests.exceptions.Timeout:
        return jsonify({"answer": "AI timeout. Try again."})

    except requests.exceptions.HTTPError as e:
        print("HTTP ERROR:", e)
        return jsonify({"answer": "AI service error. Try later."})

    except Exception:
        print("SERVER ERROR:")
        traceback.print_exc()
        return jsonify({"answer": "Server busy. Try again shortly."})


# ------------------ Run ------------------
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=False
    )