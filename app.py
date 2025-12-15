from flask import Flask, request, jsonify, send_from_directory, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from flask_session import Session
from dotenv import load_dotenv
import requests
import os
import atexit # For server shutdown cleanup
import shutil # For file system cleanup

load_dotenv()

app = Flask(__name__)
# Enable CORS for all domains
CORS(app)

# --- Configuration ---
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
MAX_CONTEXT_QA = 3  # Keep last 3 Q&A pairs (6 entries: 3 User + 3 AI)
MAX_CONTEXT_LENGTH = 1500 # Max character length for context before summarization

# Session config (server-side)
SESSION_FILE_DIR = os.path.join(os.getcwd(), 'flask_session_data') # Define session directory
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = SESSION_FILE_DIR
app.config['SECRET_KEY'] = os.getenv("APP_SECRET_TOKEN", "defaultsecret123")
Session(app)

# Rate limit: 10 requests per minute per IP
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)

# --- Utility Functions ---

def summarize_context(history_list: list[str]) -> str | None:
    """Uses the Gemini API to summarize the chat history."""
    if not API_KEY:
        print("API_KEY is missing for summarization.")
        return None

    # Join the context into a single string
    full_history = "\n".join(history_list)
    
    # Summarization prompt
    summary_prompt = (
        "Condense the following conversation history into a brief, single-paragraph "
        "summary of the key topic, ensuring all essential facts (like names, numbers, "
        "or previous results) are preserved. This summary must be used as the new context "
        "to continue the conversation. Do not add any conversational text like 'The user has asked...'. "
        f"Context to summarize: \n\n{full_history}"
    )

    url = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": API_KEY}
    
    # Structured request for summarization
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": summary_prompt}]}
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, params=params, json=payload, timeout=10)
        response.raise_for_status()
        ai_data = response.json()
        
        reply = ai_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        
        if reply:
            return f"[Context Summary]: {reply}"
        
    except requests.exceptions.RequestException as e:
        print(f"Error during context summarization: {e}")
        return None
        
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

# Register the cleanup function to run when the interpreter exits (server shuts down)
atexit.register(cleanup_on_shutdown)


# --- Routes ---

@app.route("/")
def home():
    """Serves the frontend file."""
    # Ensure index.html is in the same directory as this script
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

        # Initialize context list for the session
        if 'context' not in session:
            session['context'] = []
            
        history = session['context']

        # 1. Context Management and Summarization
        
        # Check if history is too long (using a simple character count)
        full_history_length = len("\n".join(history))
        
        # If the history is too long (and has more than the max QA pairs), summarize it
        if full_history_length > MAX_CONTEXT_LENGTH and len(history) > MAX_CONTEXT_QA * 2:
            print("History is long, attempting summarization...")
            summary = summarize_context(history)
            
            if summary:
                # Replace history with the summary
                history = [summary] 
                print("Context successfully summarized.")
            else:
                # If summarization fails, fall back to trimming the raw history
                print("Summarization failed. Trimming raw history.")
                history = history[-MAX_CONTEXT_QA * 2:]
        elif len(history) > MAX_CONTEXT_QA * 2:
            # If not too long, but over the max Q&A count, just trim it
            history = history[-MAX_CONTEXT_QA * 2:]
        
        # Add the new user question to the (potentially trimmed/summarized) history
        history.append(f"User: {question}")
        
        # 2. Build Prompt and API Call
        
        # The system instruction guides the AI's behavior
        system_instruction = (
            "You are a helpful and concise AI assistant. You must continue the conversation "
            "based on the provided context or previous turns. Be aware of the context and "
            "remember previous calculation results or facts provided by the user."
        )

        # Build the final prompt for the API call
        # The context (history) is used to construct the conversation turns.
        # The last entry is the new 'User: ' question.
        
        # Combine the entire history for the final 'contents' payload
        # This builds a 'multiturn' conversation for the Gemini API
        contents = [{"role": "user" if i % 2 == 0 else "model", "parts": [{"text": h.split(': ', 1)[1]}]} 
                    for i, h in enumerate(history) if h.startswith("User: ") or h.startswith("AI: ")]
        
        # If a summary was used, it becomes the first 'user' turn with the instruction
        if history and history[0].startswith("[Context Summary]"):
             # The summary text must be added to the *system* instruction or as a preceding user turn
             system_instruction += f"\n\nPrevious Conversation Summary: {history[0].split(': ', 1)[1]}"
             # Remove the summary from the list of turns
             contents = contents[1:] 

        # The last item in contents is the current user question.
        
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
            # Check for block reasons if no candidates
            prompt_feedback = ai_data.get("promptFeedback", {}).get("blockReason")
            block_msg = f"Prompt blocked: {prompt_feedback}" if prompt_feedback else "⚠️ No valid response from AI."
            return jsonify({"answer": block_msg}), 500

        reply = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()

        # 3. Update Session Context
        
        # Append the new AI reply to the history (in memory for this request)
        history.append(f"AI: {reply}") 
        
        # Save the updated history back to the session, including the new Q&A
        session['context'] = history
        session.modified = True

        return jsonify({"answer": reply})

    except requests.exceptions.Timeout:
        return jsonify({"answer": "⏳ AI took too long. Please retry."}), 504
    except requests.exceptions.RequestException as e:
        print("Request Exception:", e)
        # Log the specific error details from the API response if available
        try:
            error_data = response.json()
            print("API Error Details:", error_data)
        except:
            pass
        return jsonify({"answer": "🌐 Network/API error. Try again later."}), 502
    except Exception as e:
        print("Internal Error:", e)
        return jsonify({"answer": f"❌ Internal server error: {e}"}), 500

@app.route("/clear-session", methods=["POST"])
def clear_session():
    """Manually clears the user's current session context."""
    session.pop('context', None)
    return jsonify({"status": "cleared", "message": "Chat context cleared for this session."})

if __name__ == "__main__":
    # Create the session directory if it doesn't exist
    if not os.path.exists(SESSION_FILE_DIR):
        os.makedirs(SESSION_FILE_DIR)
        
    print(f"Starting server. Session files will be stored in: {SESSION_FILE_DIR}")
    
    # Note: Flask's default development server (werkzeug) often uses auto-reload,
    # which can trigger 'atexit' multiple times. In a production environment (like Gunicorn),
    # 'atexit' is more reliable for a single shutdown event.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True, use_reloader=False)

