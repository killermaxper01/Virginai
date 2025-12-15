from flask import Flask, request, jsonify, send_from_directory, session
from flask_limiter import Limiter
from flask_cors import CORS
from flask_session import Session
from dotenv import load_dotenv
import requests
import os
import atexit 
import shutil 
import time

load_dotenv()

# --- Configuration ---
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
MAX_CONTEXT_QA = 3          # Keep last 3 Q&A pairs (6 entries)
MAX_CONTEXT_LENGTH = 1500   # Max character length for history before summarization
MIN_REQUEST_DELAY = 0.1     # Small delay to discourage rapid-fire scripts

app = Flask(__name__)
CORS(app)

# Session config (server-side)
SESSION_FILE_DIR = os.path.join(os.getcwd(), 'flask_session_data') 
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = SESSION_FILE_DIR
app.config['SECRET_KEY'] = os.getenv("APP_SECRET_TOKEN", "defaultsecret123")
Session(app)

# --- Rate Limiter Setup ---
def get_client_ip():
    """Tries to get the real client IP from X-Forwarded-For headers (for proxies/load balancers)."""
    if request.headers.getlist("X-Forwarded-For"):
        # The true client IP is usually the first address in the list
        return request.headers.getlist("X-Forwarded-For")[0]
    return request.remote_addr

limiter = Limiter(
    key_func=get_client_ip, # Use the robust IP function
    app=app,
    default_limits=["10 per minute"] # Default limit for all routes
)


# --- Utility Functions ---

def summarize_context(history_list: list[str]) -> str | None:
    """Uses the Gemini API to summarize the chat history for token saving."""
    if not API_KEY:
        print("API_KEY is missing for summarization.")
        return None

    full_history = "\n".join(history_list)
    summary_prompt = (
        "Condense the following conversation history into a brief, single-paragraph "
        "summary of the key topic, ensuring all essential facts (like names, numbers, "
        "or previous calculation results) are preserved. This summary must be used as the new context "
        "to continue the conversation. Do not add any conversational text like 'The user has asked...'. "
        f"Context to summarize: \n\n{full_history}"
    )

    url = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": API_KEY}
    
    payload = {"contents": [{"role": "user", "parts": [{"text": summary_prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, params=params, json=payload, timeout=10)
        response.raise_for_status()
        ai_data = response.json()
        
        reply = ai_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        
        return f"[Context Summary]: {reply}" if reply else None
        
    except requests.exceptions.RequestException as e:
        print(f"Error during context summarization: {e}")
        return None

def cleanup_on_shutdown():
    """Clears the file system session directory on server shutdown."""
    print("\n\n--- Cleaning up sessions on server shutdown... ---")
    try:
        if os.path.exists(SESSION_FILE_DIR):
            shutil.rmtree(SESSION_FILE_DIR)
            print(f"Successfully removed session directory: {SESSION_FILE_DIR}")
    except OSError as e:
        print(f"Error during session cleanup: {e}")

# Register the cleanup function to run when the server shuts down
atexit.register(cleanup_on_shutdown)

# --- Request Hooks ---

@app.before_request
def bot_deterrent_delay():
    """Implements a small delay on POST requests to discourage rapid-fire scripts."""
    if request.method == "POST":
        time.sleep(MIN_REQUEST_DELAY)

# --- Routes ---

@app.route("/")
def home():
    """Serves the frontend file."""
    return send_from_directory(".", "index.html")

@app.route("/ask", methods=["POST"])
@limiter.limit("10 per minute")
def ask():
    """Handles the user question, manages context, and calls the Gemini API."""
    try:
        data = request.get_json(force=True)
        question = data.get("question", "").strip()

        if not question:
            return jsonify({"answer": "❗ Please type a question."}), 400
        if not API_KEY:
            return jsonify({"answer": "⚠️ Server misconfiguration (API Key missing)."}), 500

        if 'context' not in session:
            session['context'] = []
            
        history = session['context']

        # 1. Context Management and Summarization
        full_history_length = len("\n".join(history))
        
        if full_history_length > MAX_CONTEXT_LENGTH and len(history) > MAX_CONTEXT_QA * 2:
            print("History is long, attempting summarization...")
            summary = summarize_context(history)
            
            if summary:
                history = [summary] 
            else:
                # If summarization fails, fall back to trimming the raw history
                print("Summarization failed. Trimming raw history.")
                history = history[-MAX_CONTEXT_QA * 2:]
        elif len(history) > MAX_CONTEXT_QA * 2:
            # If not too long, but over the max Q&A count, just trim it
            history = history[-MAX_CONTEXT_QA * 2:]
        
        # Add the new user question to the history
        history.append(f"User: {question}")
        
        # 2. Build Prompt and API Call
        
        system_instruction = (
            "You are a helpful and concise AI assistant. You must continue the conversation "
            "based on the provided context. Be aware of the context and remember previous "
            "calculation results or facts provided by the user."
        )

        # Build the multiturn 'contents' payload
        contents = []
        for i, h in enumerate(history):
            role = None
            text = h.split(': ', 1)[1] if ': ' in h else h

            if h.startswith("User: "):
                role = "user"
            elif h.startswith("AI: "):
                role = "model"
            elif h.startswith("[Context Summary]"):
                # If using a summary, prepend it to the system instruction
                system_instruction += f"\n\nPrevious Conversation Summary: {text}"
                continue # Skip adding the summary as a turn

            if role:
                 contents.append({"role": role, "parts": [{"text": text}]})

        # Final payload structure for the API
        payload = {
            "config": {
                "systemInstruction": system_instruction
            },
            "contents": contents
        }

        url = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": API_KEY}
        
        response = requests.post(url, headers=headers, params=params, json=payload, timeout=20)
        response.raise_for_status()
        ai_data = response.json()

        candidates = ai_data.get("candidates")
        if not candidates:
            block_msg = ai_data.get("promptFeedback", {}).get("blockReason", "⚠️ No valid response from AI.")
            return jsonify({"answer": f"API Error: {block_msg}"}), 500

        reply = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()

        # 3. Update Session Context
        
        # Append the new AI reply to the history
        history.append(f"AI: {reply}") 
        
        # Save the updated history back to the session
        session['context'] = history
        session.modified = True

        return jsonify({"answer": reply})

    except requests.exceptions.Timeout:
        return jsonify({"answer": "⏳ AI took too long. Please retry."}), 504
    except requests.exceptions.RequestException as e:
        print(f"Request Exception: {e}")
        return jsonify({"answer": "🌐 Network/API error. Try again later."}), 502
    except Exception as e:
        print(f"Internal Error: {e}")
        return jsonify({"answer": "❌ Internal server error."}), 500

@app.route("/clear-session", methods=["POST"])
def clear_session():
    """Manually clears the user's current session context."""
    session.pop('context', None)
    return jsonify({"status": "cleared", "message": "Chat context cleared for this session."})

if __name__ == "__main__":
    if not os.path.exists(SESSION_FILE_DIR):
        os.makedirs(SESSION_FILE_DIR)
        
    print(f"Starting server. Session files will be stored in: {SESSION_FILE_DIR}")
    
    # Use gunicorn for production, but Flask's built-in server for local testing.
    # The `use_reloader=False` prevents atexit from being called twice during development reload.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True, use_reloader=False)
