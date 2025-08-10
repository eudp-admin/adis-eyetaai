from flask import Flask, render_template, request, jsonify
# from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required  # <-- አስወግደናል
# from flask_dance.contrib.google import make_google_blueprint, google # <-- አስወግደናል
from dotenv import load_dotenv
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import traceback

# .env ፋይሉን እንዲያነብ
load_dotenv()

# --- ሚስጥራዊ ቁልፎችን ማንበብ ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY") # ለ session አሁንም ያስፈልጋል

if not GEMINI_API_KEY or not FLASK_SECRET_KEY:
    raise ValueError("ስህተት: GEMINI_API_KEY ወይም FLASK_SECRET_KEY በ .env ፋይል ውስጥ አልተገኘም።")
# ----------------------------------------------------

# --- Flask አፕሊኬሽን ማዋቀር ---
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

# --- ★★★ ሎግኢን ሙሉ በሙሉ ተወግዷል ★★★ ---
# LoginManager, User class, google_bp, እና ሁሉም የሎግኢን መንገዶች (routes) ተወግደዋል።
# ----------------------------------------------------

# --- Gemini AI ሞዴል ማዋቀር ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    safety_settings = { HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE }
    model = genai.GenerativeModel('gemini-1.5-pro', safety_settings=safety_settings)
except Exception as e:
    print(f"የ Gemini ሞዴል ዝግጅት ላይ ስህተት አለ: {e}")

# --- ★★★ ተስተካክሏል፡ ዋናው ገጽ አሁን ሎግኢን አይጠይቅም ★★★ ---
@app.route("/")
def index():
    # ለጊዜው "User" የሚል ስም እንጠቀማለን
    return render_template("index.html", user_name="ተጠቃሚ")

# --- ★★★ ተስተካክሏል፡ /ask መንገድ ላይ @login_required ተወግዷል ★★★ ---
@app.route('/ask', methods=['POST'])
def ask():
    data = request.json
    user_question = data.get('question', '')
    client_history = data.get('history', [])
    
    if not user_question:
        return jsonify({'error': 'No question provided'}), 400

    try:
        gemini_history = []
        for item in client_history:
            if 'role' in item and 'parts' in item:
                 gemini_history.append(item)

        system_instruction = "አንተ 'አዲስ እይታ' የተባልህ፣ በኢትዮጵያ ፖለቲካ፣ ታሪክ እና ማህበራዊ ጉዳዮች ላይ የተካንክ የ AI ረዳት ነህ። መልሶችህ ሚዛናዊ、 በጥልቀት የተተነተኑ、 እና ከተለያዩ አቅጣጫዎች የሚመለከቱ መሆን አለባቸው። ማስረጃን መሰረት ያደረጉ እና ገለልተኛ አቋም የሚያንጸባርቁ መልሶችን ስጥ። ከፖለቲካዊ ውግንና የጸዳህ ሁን።"
        
        if not gemini_history:
             initial_context = [
                {'role': 'user', 'parts': [system_instruction]},
                {'role': 'model', 'parts': ["እሺ፣ ገብቶኛል። የተሰጠኝን መመሪያ መሰረት በማድረግ ሚዛናዊ እና ጥልቅ ትንታኔ እሰጣለሁ። ስለ ኢትዮጵያ ፖለቲካ፣ ታሪክ እና ማህበራዊ ጉዳዮች ምን ልርዳዎት?"]}
             ]
             gemini_history.extend(initial_context)

        chat = model.start_chat(history=gemini_history)
        response = chat.send_message(user_question)
        
        return jsonify({
            'answer': response.text,
            'new_history': [h.to_dict() for h in chat.history]
        })
    except Exception as e:
        print(f"API Error in /ask: {e}")
        traceback.print_exc()
        return jsonify({'answer': "ይቅርታ፣ ስህተት አጋጥሟል። እባክዎ እንደገና ይሞክሩ።"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
