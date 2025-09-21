from flask import Flask, request, jsonify, send_from_directory
import os
import sys
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import base64, re, cv2
import numpy as np
from deepface import DeepFace
import csv

# Sample resource data (later you can load from DB if needed)
RESOURCES = [
    {
        "title": "Stress Management Guide (Hindi)",
        "description": "Practical PDF guide in Hindi for reducing stress.",
        "type": "pdf",
        "url": "/static/resources/stress_guide_hindi.pdf",
        "language": "Hindi"
    },
    {
        "title": "Guided Meditation (English)",
        "description": "10-minute meditation audio in English.",
        "type": "audio",
        "url": "/static/resources/meditation.mp3",
        "language": "English"
    },
    {
        "title": "Stress Tips (English)",
        "description": "Quick stress relief techniques in English (PDF).",
        "type": "pdf",
        "url": "/static/resources/stress_tips_english.pdf",
        "language": "English"
    },
    {
        "title": "Relaxing Music (Universal)",
        "description": "Calming instrumental music for relaxation.",
        "type": "audio",
        "url": "/static/resources/calm_music.mp3",
        "language": "Universal"
    },
    {
        "title": "Understanding Anxiety (Video)",
        "description": "Educational video explaining anxiety and coping strategies.",
        "type": "video",
        "url": "https://www.youtube.com/embed/2ZKN5bFsY3M",
        "language": "English"
    }
]






# -----------------------------
# Setup paths
# -----------------------------
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE)
STATIC_DIR = os.path.join(BASE, "static")

# -----------------------------
# Sentiment Analyzer (VADER)
# -----------------------------
try:
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    SIA = SentimentIntensityAnalyzer()
    SIA_AVAILABLE = True
except Exception as e:
    print("⚠️ Sentiment not available:", e)
    SIA_AVAILABLE = False

# -----------------------------
# Flask app
# -----------------------------
app = Flask(__name__, static_folder=STATIC_DIR, template_folder=STATIC_DIR)

# -----------------------------
# MySQL Config (update as needed)
# -----------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Rosh@232006",   # change if needed
    "database": "mental_health"
}


def ensure_mysql_db():
    """
    Ensure the database exists (connects without 'database' key then creates it).
    """
    cfg = DB_CONFIG.copy()
    db_name = cfg.pop("database", None)
    if not db_name:
        return
    conn = mysql.connector.connect(**cfg)
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET 'utf8'")
    conn.commit()
    cursor.close()
    conn.close()


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


# -----------------------------
# Init Tables
# -----------------------------
def init_mysql_tables():
    ensure_mysql_db()
    conn = get_connection()
    cursor = conn.cursor()

    # users table with email included
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) UNIQUE,
            email VARCHAR(255) UNIQUE,
            password VARCHAR(255)
        )
    """)

    # chat_logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            message TEXT,
            sentiment_score FLOAT,
            sentiment_label VARCHAR(20),
            suggestion TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # questionnaire_responses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questionnaire_responses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            stress_score FLOAT,
            anxiety_score FLOAT,
            depression_score FLOAT,
            social_support FLOAT,
            parental_relation FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # -------------------------------
    # NEW: Peer Support tables
    # -------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS peer_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS peer_replies (
            id INT AUTO_INCREMENT PRIMARY KEY,
            message_id INT,
            user_id INT,
            text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES peer_messages(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS peer_reactions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            message_id INT,
            user_id INT,
            emoji VARCHAR(10),
            FOREIGN KEY (message_id) REFERENCES peer_messages(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS peer_mood (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            mood VARCHAR(10),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()


def init_admin_table():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE,
                password VARCHAR(255)
            )
        """)
        # Ensure default admin exists
        cursor.execute("SELECT id FROM admins WHERE username=%s", ("admin",))
        row = cursor.fetchone()
        if not row:
            hashed = generate_password_hash("admin123")
            cursor.execute(
                "INSERT INTO admins (username, password) VALUES (%s,%s)",
                ("admin", hashed)
            )
            conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print("⚠️ init_admin_table error:", e)



# -----------------------------
# User Helpers
# -----------------------------
def add_user(username, email, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
        (username, email, password)
    )
    conn.commit()
    user_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return user_id


def get_user_by_email(email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, email, password FROM users WHERE email=%s",
        (email,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return {"id": row[0], "username": row[1], "email": row[2], "password": row[3]}
    return None


def get_user(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, email, password FROM users WHERE username=%s",
        (username,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return {"id": row[0], "username": row[1], "email": row[2], "password": row[3]}
    return None


# Init tables at startup
init_mysql_tables()
init_admin_table()

# -----------------------------
# Suggestion logic (chat)
# -----------------------------
def get_suggestion(score, text=""):
    text = (text or "").lower()

    # Keyword-based detection first
    if any(word in text for word in ["tired", "exhausted", "fatigued", "sleepy", "drowsy"]):
        return "It sounds like you're feeling tired. Try taking a short rest, staying hydrated, or adjusting your sleep routine."
    if any(word in text for word in ["anxious", "worried", "nervous", "tense"]):
        return "I sense some anxiety. Deep breathing or journaling your thoughts may help calm your mind."
    if any(word in text for word in ["angry", "frustrated", "mad", "furious"]):
        return "It seems like you're upset. Taking a break or practicing relaxation techniques might help."
    if any(word in text for word in ["sad", "lonely", "depressed", "down"]):
        return "I hear some sadness in your words. Talking to a close friend or engaging in a hobby may lift your mood."

    # Fallback to sentiment-score ranges
    if score <= -0.5:
        return "Your input indicates high stress. Try deep breathing for a few minutes and consider sharing your thoughts with someone you trust."
    elif -0.5 < score <= -0.2:
        return "Your input shows moderate stress. A short walk or writing down your feelings may help calm your mind."
    elif -0.2 < score <= 0.2:
        return "Your input suggests low stress. You could try a quick relaxation exercise, like stretching or listening to music."
    else:
        return "Your input reflects no stress. Keep maintaining your positive habits and continue doing what makes you feel good."


# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "login.html")


@app.route("/<path:filename>")
def static_pages(filename):
    if os.path.exists(os.path.join(STATIC_DIR, filename)):
        return send_from_directory(STATIC_DIR, filename)
    return send_from_directory(STATIC_DIR, "login.html")


# --- Signup ---
@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.json or {}
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not username or not email or not password:
        return jsonify({"message": "missing fields"}), 400

    # Check if user exists
    user = get_user(username)
    if user:
        return jsonify({"message": "user exists"}), 400

    # Save new user
    hashed_pw = generate_password_hash(password)
    user_id = add_user(username, email, hashed_pw)

    return jsonify({
        "ok": True,
        "user_id": user_id,
        "message": "signup successful"
    }), 200


# --- Login ---
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "missing fields"}), 400

    user = get_user_by_email(email)
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"message": "invalid credentials"}), 401

    return jsonify({
        "ok": True,
        "user_id": user["id"],
        "username": user["username"],
        "email": user["email"]
    })


# --- Forgot Password ---
@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    data = request.json or {}
    email = data.get("email")

    if not email:
        return jsonify({"message": "missing email"}), 400

    user = get_user_by_email(email)
    if not user:
        return jsonify({"message": "email not found"}), 404

    return jsonify({"message": f"Password reset link sent to {email}"}), 200


# --- Admin Login ---
@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({'success': False, 'message': 'Missing credentials'}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM admins WHERE username=%s", (username,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

        admin_id, hashed = row[0], row[1]
        if check_password_hash(hashed, password):
            return jsonify({'success': True, 'admin_id': admin_id}), 200
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    except Exception as e:
        print("⚠️ admin login error:", e)
        return jsonify({'success': False, 'message': 'Server error'}), 500


# --- Admin Create (optional) ---
@app.route("/api/admin/create", methods=["POST"])
def admin_create():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({'success': False, 'message': 'Missing fields'}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM admins WHERE username=%s", (username,))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'Admin already exists'}), 400

        hashed = generate_password_hash(password)
        cursor.execute("INSERT INTO admins (username, password) VALUES (%s,%s)", (username, hashed))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Admin created successfully'}), 200
    except Exception as e:
        print("⚠️ admin_create error:", e)
        return jsonify({'success': False, 'message': 'Server error'}), 500


# --- Admin Metrics ---
@app.route('/api/admin/metrics', methods=['GET'])
def admin_metrics():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""SELECT AVG(stress_score) AS avg_stress,
                                 AVG(anxiety_score) AS avg_anxiety,
                                 AVG(depression_score) AS avg_depression,
                                 COUNT(*) AS total_entries
                          FROM questionnaire_responses""")
        agg = cursor.fetchone()

        cursor.execute("""SELECT created_at, stress_score, anxiety_score, depression_score
                          FROM questionnaire_responses
                          ORDER BY created_at DESC LIMIT 30""")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        history = [{
            'timestamp': r['created_at'].isoformat() if hasattr(r['created_at'],'isoformat') else str(r['created_at']),
            'stress': r['stress_score'],
            'anxiety': r['anxiety_score'],
            'depression': r['depression_score']
        } for r in rows]

        return jsonify({
            'avg_stress': float(agg['avg_stress']) if agg and agg['avg_stress'] else 0.0,
            'avg_anxiety': float(agg['avg_anxiety']) if agg and agg['avg_anxiety'] else 0.0,
            'avg_depression': float(agg['avg_depression']) if agg and agg['avg_depression'] else 0.0,
            'total_entries': int(agg['total_entries']) if agg and agg['total_entries'] else 0,
            'history': history
        })
    except Exception as e:
        print('⚠️ admin_metrics error:', e)
        return jsonify({'error': str(e)}), 500


# --- Chatbot (sentiment + suggestions) ---
@app.route("/api/chat", methods=["POST"])
def chat():
    payload = request.json or {}
    text = (payload.get("text") or "").strip()
    user_id = payload.get("user_id")

    if not text:
        return jsonify({"reply": "Please send a message."})

    # sentiment
    score, label = 0.0, "NEUTRAL"
    if SIA_AVAILABLE:
        s = SIA.polarity_scores(text)
        score = s.get("compound", 0.0)
        if score >= 0.05:
            label = "POSITIVE"
        elif score <= -0.05:
            label = "NEGATIVE"
        else:
            label = "NEUTRAL"

    # Generate suggestion
    suggestion = get_suggestion(score, text)

    reply = f"I hear you. (sentiment: {label}) — You said: {text}"

    # Save chat in DB
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_logs (user_id, message, sentiment_score, sentiment_label, suggestion) VALUES (%s,%s,%s,%s,%s)",
            (user_id, text, score, label, suggestion)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print("⚠️ DB insert error:", e)

    return jsonify({
        "reply": reply,
        "label": label,
        "score": score,
        "suggestion": suggestion
    })


# --- History ---
@app.route("/api/history", methods=["GET"])
def history():
    logs = []
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, user_id, message AS text, sentiment_score AS score,
                   sentiment_label AS label, suggestion, created_at
            FROM chat_logs ORDER BY created_at DESC LIMIT 200
        """)
        logs = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        print("⚠️ History DB error:", e)
    return jsonify(logs)


# --- Emotion Detection ---
@app.route("/api/emotion", methods=["POST"])
def detect_emotion():
    try:
        data = request.json["image"]
        image_data = re.sub("^data:image/.+;base64,", "", data)
        img_bytes = base64.b64decode(image_data)
        img_array = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        analysis = DeepFace.analyze(frame, actions=["emotion"], enforce_detection=False)
        dominant_emotion = analysis[0]["dominant_emotion"]

        return jsonify({"emotion": dominant_emotion})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/face_recognition", methods=["POST"])
def face_recognition_alias():
    return detect_emotion()


# -----------------------------
# Questionnaire helpers + endpoints
# -----------------------------
def _scale_avg_to_100(avg):
    try:
        a = float(avg)
        return max(0.0, min(100.0, ((a - 1.0) / 4.0) * 100.0))
    except:
        return 0.0


def get_questionnaire_suggestions(stress_score, anxiety_score, depression_score, social_support, parental_relation):
    tips = []
    if depression_score >= 75:
        tips.append("Your responses indicate a high level of depressive symptoms. Please consider reaching out to a mental health professional or school counselor.")
    if anxiety_score >= 75:
        tips.append("High anxiety detected — try grounding techniques: 4-4-4 breathing (inhale 4s, hold 4s, exhale 4s) and practice short relaxation breaks.")
    if stress_score >= 75:
        tips.append("High stress detected — schedule short breaks, break tasks into small steps, and ensure regular sleep.")
    if social_support < 40:
        tips.append("You may benefit from increasing social connections: join a club, study group, or extracurricular activity.")
    if parental_relation < 40:
        tips.append("Consider opening a small conversation with your parents/guardians about how you feel; start with one positive thing per day.")
    if 50 <= stress_score < 75:
        tips.append("Moderate stress — try time-blocking your study schedule and brief mindfulness exercises.")
    if 50 <= anxiety_score < 75:
        tips.append("Moderate anxiety — prepare for upcoming exams with a study plan and relaxation before bed.")
    if 50 <= depression_score < 75:
        tips.append("Moderate depressive signs — increase daily activities you enjoy and consider talking to a friend or mentor.")
    if stress_score < 25 and anxiety_score < 25 and depression_score < 25:
        tips.append("Your scores are in the low range — keep up healthy routines: sleep, hydration, and social time.")
    if not tips:
        tips.append("Keep monitoring your mental health. Small daily routines can help: sleep, move, and talk to someone you trust.")
    return tips


@app.route("/api/questionnaire", methods=["POST"])
def questionnaire():
    data = request.json or {}
    user_id = data.get("user_id") or 1
    stress_answers = data.get("stress", [])
    anxiety_answers = data.get("anxiety", [])
    depression_answers = data.get("depression", [])
    social_answers = data.get("social", [])
    parental_relation = data.get("parental_relation", [])

    def avg(arr):
        if not arr:
            return 0.0
        vals = []
        for v in arr:
            try:
                vals.append(float(v))
            except:
                pass
        if not vals:
            return 0.0
        return sum(vals) / len(vals)

    stress_avg = avg(stress_answers)
    anxiety_avg = avg(anxiety_answers)
    depression_avg = avg(depression_answers)
    social_avg = avg(social_answers)
    parental_avg = avg(parental_relation)

    stress_score = _scale_avg_to_100(stress_avg)
    anxiety_score = _scale_avg_to_100(anxiety_avg)
    depression_score = _scale_avg_to_100(depression_avg)
    social_support = _scale_avg_to_100(social_avg)
    parental_relation_score = _scale_avg_to_100(parental_avg)

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO questionnaire_responses
            (user_id, stress_score, anxiety_score, depression_score, social_support, parental_relation)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (user_id, stress_score, anxiety_score, depression_score, social_support, parental_relation_score))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print("Questionnaire DB insert error:", e)

    history = []
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""SELECT created_at, stress_score, anxiety_score, depression_score
                          FROM questionnaire_responses
                          WHERE user_id=%s ORDER BY created_at DESC LIMIT 90""", (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        history = [{"timestamp": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
                    "stress": r["stress_score"], "anxiety": r["anxiety_score"], "depression": r["depression_score"]} for r in rows]
    except Exception as e:
        print("Questionnaire history read error:", e)

    return jsonify({
        "ok": True,
        "stress_score": stress_score,
        "anxiety_score": anxiety_score,
        "depression_score": depression_score,
        "social_support": social_support,
        "parental_relation": parental_relation_score,
        "history": history,
        "suggestions": get_questionnaire_suggestions(stress_score, anxiety_score, depression_score, social_support, parental_relation_score)
    })


@app.route("/api/questionnaire/history", methods=["GET"])
def questionnaire_history():
    user_id = request.args.get("user_id", type=int) or 1
    items = []
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""SELECT created_at, stress_score, anxiety_score, depression_score
                          FROM questionnaire_responses
                          WHERE user_id=%s ORDER BY created_at DESC LIMIT 365""", (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        items = [{"timestamp": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
                  "stress": r["stress_score"], "anxiety": r["anxiety_score"], "depression": r["depression_score"]} for r in rows]
    except Exception as e:
        print("Questionnaire history fetch error:", e)
    return jsonify(items)

# -----------------------------
# Load Emergency Contacts from CSV
# -----------------------------
@app.route("/api/emergency/contacts", methods=["GET"])
def emergency_contacts():
    contacts = []
    try:
        with open(os.path.join(BASE, "data", "50_psychiatry_online_links_india.csv"), encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get("name") or "").strip()
                phone = (row.get("phone") or "").strip()
                location = (row.get("location") or "").strip()
                link = (row.get("link") or "").strip()

                # Skip empty or "Unknown" entries
                if not name or name.lower() == "unknown":
                    continue  

                contacts.append({
                    "name": name,
                    "phone": phone if phone else "N/A",
                    "location": location if location else "N/A",
                    "link": link if link else "#"
                })
    except Exception as e:
        print("⚠️ emergency_contacts error:", e)
    return jsonify(contacts)
# --- Peer Support APIs ---
@app.route("/api/peer/messages", methods=["GET"])
def get_peer_messages():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM peer_messages ORDER BY created_at DESC LIMIT 50")
    msgs = cursor.fetchall()

    result = []
    for m in msgs:
        cursor.execute("SELECT text, user_id FROM peer_replies WHERE message_id=%s", (m["id"],))
        replies = cursor.fetchall()

        cursor.execute("SELECT emoji, COUNT(*) as count FROM peer_reactions WHERE message_id=%s GROUP BY emoji", (m["id"],))
        reactions = {r["emoji"]: r["count"] for r in cursor.fetchall()}

        # pseudo anonymous user
        pseudo = f"Peer#{m['user_id']}"
        result.append({
            "id": m["id"],
            "user": pseudo,
            "text": m["text"],
            "replies": [{"text": r["text"], "user": f"Peer#{r['user_id']}"} for r in replies],
            "reactions": reactions,
            "badge": "🌟 Supportive" if len(replies) > 3 else None
        })

    cursor.close()
    conn.close()
    return jsonify(result)


@app.route("/api/peer/message", methods=["POST"])
def post_peer_message():
    data = request.json
    text = data.get("text")
    user_id = 1  # TODO: get from session
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO peer_messages (user_id, text) VALUES (%s,%s)", (user_id, text))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/peer/reply", methods=["POST"])
def post_peer_reply():
    data = request.json
    message_id, text = data.get("message_id"), data.get("text")
    user_id = 1
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO peer_replies (message_id, user_id, text) VALUES (%s,%s,%s)", (message_id, user_id, text))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/peer/react", methods=["POST"])
def post_peer_react():
    data = request.json
    message_id, emoji = data.get("message_id"), data.get("emoji")
    user_id = 1
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO peer_reactions (message_id, user_id, emoji) VALUES (%s,%s,%s)", (message_id, user_id, emoji))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/peer/mood", methods=["POST"])
def post_peer_mood():
    data = request.json
    mood = data.get("mood")
    user_id = 1
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO peer_mood (user_id, mood) VALUES (%s,%s)", (user_id, mood))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"ok": True})

@app.route("/resource-hub")
def resource_hub():
    # Serve your static HTML file
    return send_from_directory("static", "resource_hub.html")
# -----------------------------
# Run app
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
