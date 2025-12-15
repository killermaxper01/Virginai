from flask import Flask, request, jsonify, render_template
import requests
import os

app = Flask(__name__)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    user_question = request.json.get("question")

    url = (
        f"https://generativelanguage.googleapis.com/v1/"
        f"models/{MODEL}:generateContent?key={API_KEY}"
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_question}]
            }
        ]
    }

    try:
        r = requests.post(url, json=payload, timeout=20)
        data = r.json()
        answer = data["candidates"][0]["content"]["parts"][0]["text"]
        return jsonify({"answer": answer})

    except Exception:
        return jsonify({"answer": "Server error. Please try again."})

if __name__ == "__main__":
    app.run()
