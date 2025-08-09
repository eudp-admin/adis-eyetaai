from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_dance.contrib.google import make_google_blueprint, google
from dotenv import load_dotenv
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# .env ፋይሉን እንዲያነብ
load_dotenv()

# --- ★★★★★ ወሳኝ የማረጋገጫ ክፍል ★★★★★ ---
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not all([FLASK_SECRET_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GEMINI_API_KEY]):
    raise ValueError("ስህተት: በ .env ፋይል ውስጥ ከሚስጥራዊ ቁልፎች አንዱ አልተገኘም። እባክዎ ሁሉንም ቁልፎች ያስገቡ።")
# ----------------------------------------------------

# --- ★★★★★ ወሳኝ ማስተካከያ ★★★★★ ---
# ፕሮግራሙ በ Render ላይ እየሰራ እንደሆነ እናረጋግጣለን
IS_PRODUCTION = os.getenv("RENDER") == "true"

if IS_PRODUCTION:
    # በ Render ላይ ስንሆን፣ ትክክለኛው የ HTTPS አድራሻ ይህ ነው
    # 'adis-eyetaai' በሚለው ፈንታ የራስህን የ Render service ስም ተጠቀም
    redirect_uri = "https://adis-eyetaai.onrender.com/login/google/authorized"
else:
    # በኮምፒውተራችን ላይ ስንሆን፣ HTTP ላይ እንዲሰራ እንፈቅዳለን
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    redirect_uri = "http://127.0.0.1:5001/login/google/authorized"
# ----------------------------------------------------

# --- Flask አፕሊኬሽን እና ማዋቀር ---
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

# --- የተጠቃሚ መግቢያ ስርዓት ---
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

# --- Google OAuth ማዋቀር ---
google_bp = make_google_blueprint(
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    scope=["openid", "email", "profile"],
    redirect_url=redirect_uri # አሁን አስተዋይ የሆነውን አድራሻ እንጠቀማለን
)
app.register_blueprint(google_bp, url_prefix="/login")

# --- Gemini AI ሞዴል ማዋቀር ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    safety_settings = { HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE }
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
    # ... (ይህ ክፍል ምንም ለውጥ የለውም)
    if not google.authorized:
        return redirect(url_for("login"))
    
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok: return "Failed to fetch user info from Google.", 500
        
    user_info = resp.json()
    user_id = str(user_info["id"])
    
    user = User(id=user_id, name=user_info.get("name", "N/A"), email=user_info.get("email", "N/A"))
    users[user_id] = user
    login_user(user)
    
    session["chat_history"] = []
    
    return redirect(url_for("index"))

@app.route("/logout")
@login_required
def logout():
    session.pop("chat_history", None)
    logout_user()
    return redirect(url_for("login"))

@app.route('/ask', methods=['POST'])
@login_required
def ask():
    user_question = request.json.get('question', '')
    chat_history = session.get("chat_history", [])
    
    try:
        system_instruction = """
        አንተ 'አዲስ እይታ' የተባልክ፣ ገለልተኛ የኢትዮጵያ ፖለቲካ ተንታኝ እና የታሪክ ምሁር AI ነህ።
        አላማህ ለተጠቃሚዎች ውስብስብ የፖለቲካ እና የታሪክ ጥያቄዎችን ሚዛናዊ በሆነ መንገድ ማስረዳት ነው።
        መልስህን በደንብ አደራጅተህ፣ በነጥብ በነጥብ (bullet points) እና በንዑስ ርዕሶች ከፋፍለህ አቅርብ።
        """
        chat = model.start_chat(history=chat_history or [{'role': 'user', 'parts': [system_instruction]}, {'role': 'model', 'parts': ["እሺ፣ ገብቶኛል።"]}])
        response = chat.send_message(user_question)
        session["chat_history"] = chat.history
        return jsonify({'answer': response.text})
    except Exception as e:
        print(f"API Error: {e}")
        return jsonify({'answer': "ይቅርታ፣ ስህተት አጋጥሟል። እባክዎ እንደገና ይሞክሩ።"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
