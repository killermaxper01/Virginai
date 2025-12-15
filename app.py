INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>VirginAI</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{
    margin:0;
    font-family:Arial, sans-serif;
    background:linear-gradient(135deg,#141E30,#243B55);
    color:white;
    display:flex;
    justify-content:center;
    align-items:center;
    height:100vh;
}
.app{
    width:100%;
    max-width:500px;
    height:85vh;
    background:rgba(255,255,255,0.05);
    border-radius:15px;
    display:flex;
    flex-direction:column;
    padding:15px;
}
h2{text-align:center;color:#00c6ff;margin:5px 0;}
#chat{
    flex:1;
    overflow-y:auto;
    padding:10px;
    border-radius:10px;
    background:rgba(0,0,0,0.3);
    white-space:pre-wrap;
}
.msg{
    margin:8px 0;
    padding:10px;
    border-radius:10px;
}
.user{background:#00c6ff55;text-align:right;}
.ai{background:#4444ff55;}
textarea{
    width:100%;
    resize:vertical;
    min-height:60px;
    max-height:120px;
    padding:10px;
    border-radius:10px;
    border:none;
    outline:none;
}
button{
    margin-top:8px;
    padding:12px;
    border:none;
    border-radius:10px;
    font-size:16px;
    cursor:pointer;
}
.ask{background:#00c6ff;color:white;}
.clear{background:#ff5555;color:white;}
</style>
</head>
<body>
<div class="app">
<h2>🤖 VirginAI</h2>
<div id="chat"></div>
<textarea id="q" placeholder="Ask anything (multi-line allowed)"></textarea>
<button class="ask" onclick="ask()">Ask</button>
<button class="clear" onclick="clearChat()">Clear Chat</button>
</div>

<script>
const chat=document.getElementById("chat");
const q=document.getElementById("q");

function add(text,cls){
 const d=document.createElement("div");
 d.className="msg "+cls;
 d.textContent=text;
 chat.appendChild(d);
 chat.scrollTop=chat.scrollHeight;
}

async function ask(){
 const text=q.value.trim();
 if(!text) return;
 add(text,"user");
 q.value="";
 add("Thinking...","ai");

 const r=await fetch("/ask",{
   method:"POST",
   headers:{"Content-Type":"application/json"},
   body:JSON.stringify({question:text})
 });
 const d=await r.json();
 chat.lastChild.remove();
 add(d.answer,"ai");
}

async function clearChat(){
 chat.innerHTML="";
 await fetch("/clear-session",{method:"POST"});
}
</script>
</body>
</html>
"""


from flask import Flask, request, jsonify, session, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
import requests, os

load_dotenv()

app = Flask(__name__)
CORS(app)

# ---- Security & Session ----
app.secret_key = os.getenv("APP_SECRET_TOKEN", "change_this_secret")
app.config["SESSION_PERMANENT"] = False  # clears when browser closes

# ---- Rate Limiter (per IP) ----
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
MAX_CONTEXT = 4   # last 4 Q&A only

# -----------------------------
@app.route("/")
def home():
    return Response(INDEX_HTML, mimetype="text/html")

# -----------------------------
@app.route("/ask", methods=["POST"])
@limiter.limit("10 per minute")
def ask():
    try:
        data = request.get_json()
        question = data.get("question", "").strip()

        if not question:
            return jsonify({"answer": "❗ Please enter a question."})

        if "context" not in session:
            session["context"] = []

        # Add user message
        session["context"].append(f"User: {question}")

        # Trim context
        session["context"] = session["context"][-MAX_CONTEXT*2:]

        prompt = "\n".join(session["context"]) + "\nAI:"

        url = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent"
        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": prompt}]
            }]
        }

        response = requests.post(
            url,
            params={"key": API_KEY},
            json=payload,
            timeout=20
        )
        response.raise_for_status()

        reply = response.json()["candidates"][0]["content"]["parts"][0]["text"]

        session["context"].append(f"AI: {reply}")
        session.modified = True

        return jsonify({"answer": reply})

    except requests.exceptions.Timeout:
        return jsonify({"answer": "⏳ AI timeout. Try again."})
    except Exception as e:
        print("Error:", e)
        return jsonify({"answer": "❌ Server error. Try later."})

# -----------------------------
@app.route("/clear-session", methods=["POST"])
def clear_session():
    session.clear()
    return jsonify({"status": "cleared"})

# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))