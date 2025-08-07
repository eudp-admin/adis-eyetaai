from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_dance.contrib.google import make_google_blueprint, google
from dotenv import load_dotenv
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# .env ፋይሉን እንዲያነብ (ይህ መስመር ከሁሉም በፊት መሆን አለበት)
load_dotenv()

# --- ★★★★★ ወሳኝ የማረጋገጫ ክፍል ★★★★★ ---
# ሁሉንም ሚስጥራዊ ቁልፎች ከ .env ፋይል ላይ እናነባለን
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ቁልፎቹ መኖራቸውን እናረጋግጣለን። ከሌሉ፣ ፕሮግራሙ ወዲያው ይቆማል።
if not FLASK_SECRET_KEY:
    raise ValueError("ስህተት: FLASK_SECRET_KEY በ .env ፋይል ውስጥ አልተገኘም። እባክዎ ያስተካክሉ።")
if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    raise ValueError("ስህተት: GOOGLE_OAUTH_CLIENT_ID ወይም SECRET በ .env ፋይል ውስጥ አልተገኙም።")
if not GEMINI_API_KEY:
    raise ValueError("ስህተት: GEMINI_API_KEY በ .env ፋይል ውስጥ አልተገኘም።")
# --- Flask አፕሊኬሽን እና ማዋቀር ---
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY # አሁን በቀጥታ ከተለዋዋጩ እንወስዳለን

# --- የተጠቃሚ መግቢያ ስርዓት (Login Management) ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(UserMixin):
    def __init__(self, id, name, email):
        self.id = id
        self.name = name
        self.email = email
users = {}
@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

# --- Google OAuth ማዋቀር (Flask-Dance) ---
google_bp = make_google_blueprint(
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    scope=["openid", "email", "profile"],
    redirect_url="/login/google/authorized"
)
app.register_blueprint(google_bp, url_prefix="/login")

# --- Gemini AI ሞዴል ማዋቀር ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    safety_settings = { HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE } # Simplified for clarity
    model = genai.GenerativeModel('gemini-1.5-pro', safety_settings=safety_settings)
except Exception as e:
    print(f"የ Gemini ሞዴል ዝግጅት ላይ ስህተት አለ: {e}")

# --- የድረ-ገጽ መንገዶች (Routes) ---
@app.route("/")
@login_required
def index():
    return render_template("index.html", user_name=current_user.name)

@app.route("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/login/google/authorized")
def google_authorized():
    if not google.authorized:
        return redirect(url_for("login"))
    
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return "Failed to fetch user info from Google.", 500
        
    user_info = resp.json()
    user_id = str(user_info["id"])
    
    user = User(id=user_id, name=user_info.get("name", "N/A"), email=user_info.get("email", "N/A"))
    users[user_id] = user
    login_user(user)
    
    session[f"chat_history_{user_id}"] = []
    
    return redirect(url_for("index"))

@app.route("/logout")
@login_required
def logout():
    session.pop(f"chat_history_{current_user.id}", None)
    logout_user()
    return redirect(url_for("login"))

@app.route('/ask', methods=['POST'])
@login_required
def ask():
    user_question = request.json.get('question', '')
    user_id = current_user.id
    chat_history_key = f"chat_history_{user_id}"
    chat_history = session.get(chat_history_key, [])
    
    try:
        system_instruction = "..." # Your system instruction
        chat = model.start_chat(history=chat_history or [{'role': 'user', 'parts': [system_instruction]}, {'role': 'model', 'parts': ["እሺ፣ ገብቶኛል።"]}])
        response = chat.send_message(user_question)
        session[chat_history_key] = chat.history
        return jsonify({'answer': response.text})
    except Exception as e:
        print(f"API Error: {e}")
        return jsonify({'answer': "ይቅርታ፣ ስህተት አጋጥሟል። እባክዎ እንደገና ይሞክሩ።"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
