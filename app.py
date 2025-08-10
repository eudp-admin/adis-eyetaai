from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_dance.contrib.google import make_google_blueprint, google
from dotenv import load_dotenv
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import traceback

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

# ★★★ ተስተካክሏል ★★★
# 'users' dictionary ለቀላል ማሳያ ብቻ ነው። በትክክለኛ መተግበሪያ ዳታቤዝ መጠቀም ይመከራል።
users = {}

@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

# --- ★★★ ተስተካክሏል፡ Google OAuth ማዋቀርን ማቅለል ★★★ ---
# ውስብስብ የነበረው if/else ሙሉ በሙሉ ተወግዷል።
# Flask-Dance በራሱ ትክክለኛውን redirect_uri ከ request context መገንባት ይችላል።
# 'OAUTHLIB_INSECURE_TRANSPORT' ለ production በፍጹም አያስፈልግም።
google_bp = make_google_blueprint(
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    scope=["openid", "email", "profile"],
)
app.register_blueprint(google_bp, url_prefix="/login")
# ----------------------------------------------------

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
    if not google.authorized:
        print("Authorization with Google failed or was denied.")
        return redirect(url_for("login"))
    
    try:
        resp = google.get("/oauth2/v2/userinfo")
        
        if not resp.ok:
            print(f"ERROR: Failed to fetch user info from Google. Status: {resp.status_code}")
            print(f"ERROR BODY: {resp.text}")
            return "Failed to fetch user info from Google. Check server logs.", 500
            
        user_info = resp.json()
        user_id = str(user_info["id"])
        
        # ተጠቃሚውን መፍጠር
        user = User(id=user_id, name=user_info.get("name", "N/A"), email=user_info.get("email", "N/A"))
        users[user_id] = user
        login_user(user)
        
        # ★★★ ተስተካክሏል ★★★
        # የውይይት ታሪክን ከ session ላይ ሙሉ በሙሉ አስወግደናል
        
        return redirect(url_for("index"))
    except Exception as e:
        print("An unexpected error occurred in google_authorized function:")
        print(traceback.format_exc())
        return "An internal server error occurred.", 500


@app.route("/logout")
@login_required
def logout():
    # ★★★ ተስተካክሏል ★★★
    # የውይይት ታሪክን ከ session ላይ ሙሉ በሙሉ አስወግደናል
    # session.pop(...) አያስፈልግም
    logout_user()
    return redirect(url_for("login"))


# --- ★★★ ተስተካክሏል፡ የውይይት ታሪክ አያያዝ ★★★ ---
@app.route('/ask', methods=['POST'])
@login_required
def ask():
    data = request.json
    user_question = data.get('question', '')
    # የውይይት ታሪክን ከ request እንቀበላለን (ከ session አይደለም)
    client_history = data.get('history', [])
    
    if not user_question:
        return jsonify({'error': 'No question provided'}), 400

    try:
        # Gemini የሚቀበለውን ትክክለኛ የታሪክ መዋቅር መገንባት
        # ደንበኛው ከሚልከው ቀላል array ላይ እንገነባዋለን
        gemini_history = []
        for item in client_history:
            # a simple check for structure
            if 'role' in item and 'parts' in item:
                 gemini_history.append(item)

        system_instruction = "አንተ 'አዲስ እይታ' የተባልህ፣ በኢትዮጵያ ፖለቲካ፣ ታሪክ እና ማህበራዊ ጉዳዮች ላይ የተካንክ የ AI ረዳት ነህ። መልሶችህ ሚዛናዊ、 በጥልቀት የተተነተኑ、 እና ከተለያዩ አቅጣጫዎች የሚመለከቱ መሆን አለባቸው። ማስረጃን መሰረት ያደረጉ እና ገለልተኛ አቋም የሚያንጸባርቁ መልሶችን ስጥ። ከፖለቲካዊ ውግንና የጸዳህ ሁን።"
        
        # ታሪክ ከሌለ ብቻ የስርዓት መመሪያውን እንጨምራለን
        if not gemini_history:
             initial_context = [
                {'role': 'user', 'parts': [system_instruction]},
                {'role': 'model', 'parts': ["እሺ፣ ገብቶኛል። የተሰጠኝን መመሪያ መሰረት በማድረግ ሚዛናዊ እና ጥልቅ ትንታኔ እሰጣለሁ። ስለ ኢትዮጵያ ፖለቲካ፣ ታሪክ እና ማህበራዊ ጉዳዮች ምን ልርዳዎት?"]}
             ]
             gemini_history.extend(initial_context)

        chat = model.start_chat(history=gemini_history)
        response = chat.send_message(user_question)
        
        # ሙሉውን አዲስ ታሪክ ወደ ደንበኛው እንልካለን
        return jsonify({
            'answer': response.text,
            'new_history': [h.to_dict() for h in chat.history]
        })
    except Exception as e:
        print(f"API Error in /ask: {e}")
        traceback.print_exc()
        return jsonify({'answer': "ይቅርታ፣ ስህተት አጋጥሟል። እባክዎ እንደገና ይሞክሩ።"}), 500

if __name__ == '__main__':
    # ይህ ለ local development ብቻ ነው
    # Render የራሱን Gunicorn server ይጠቀማል
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app.run(host='0.0.0.0', port=5001, debug=True)
