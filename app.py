# import os
# os.environ["TOKENIZERS_PARALLELISM"] = "false"
# import sqlite3
# from flask import Flask, render_template, request, redirect, session, url_for, g
# from flask_mail import Mail, Message
# from itsdangerous import URLSafeTimedSerializer
# from dotenv import load_dotenv
# from werkzeug.security import generate_password_hash, check_password_hash
# from src.helper import download_hugging_face_embeddings
# from langchain_pinecone import PineconeVectorStore
# from openai import OpenAI
# from datetime import datetime

# # ----------------- Initialize app and environment -----------------
# app = Flask(__name__)
# app.secret_key = "supersecretkey"
# serializer = URLSafeTimedSerializer(app.secret_key)
# load_dotenv()

# # ----------------- Mail Config -----------------
# app.config.update(
#     MAIL_SERVER='smtp.gmail.com',
#     MAIL_PORT=587,
#     MAIL_USE_TLS=True,
#     MAIL_USERNAME=os.environ.get("EMAIL_USER"),
#     MAIL_PASSWORD=os.environ.get("EMAIL_PASS"),
#     MAIL_DEFAULT_SENDER=os.environ.get("EMAIL_USER")
# )
# mail = Mail(app)


# # ----------------- Database -----------------
# DATABASE = "users.db"

# def get_db():
#     db = getattr(g, "_database", None)
#     if db is None:
#         db = g._database = sqlite3.connect(DATABASE)
#         db.row_factory = sqlite3.Row
#     return db

# @app.teardown_appcontext
# def close_connection(exception):
#     db = getattr(g, "_database", None)
#     if db is not None:
#         db.close()

# # Create tables if not exist
# def init_db():
#     with app.app_context():
#         db = get_db()
#         cursor = db.cursor()

#         # Users table with fullname
#         cursor.execute("""
#             CREATE TABLE IF NOT EXISTS users (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 fullname TEXT NOT NULL,
#                 username TEXT UNIQUE NOT NULL,
#                 password TEXT NOT NULL
#             )
#         """)

#         # Chat history table with timestamps
#         cursor.execute("""
#             CREATE TABLE IF NOT EXISTS chat_history (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 username TEXT NOT NULL,
#                 question TEXT NOT NULL,
#                 answer TEXT NOT NULL,
#                 timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
#             )
#         """)

#         db.commit()

# # ----------------- AI and Pinecone setup -----------------
# PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
# OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
# os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY

# embeddings = download_hugging_face_embeddings()
# index_name = "medicalbot"
# docsearch = PineconeVectorStore.from_existing_index(index_name=index_name, embedding=embeddings)
# retriever = docsearch.as_retriever(search_type="similarity", search_kwargs={"k": 3})
# client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)

# # ----------------- Routes -----------------

# @app.route("/")
# def index():
#     return redirect("/login")

# # ---------- REGISTER ----------
# @app.route("/register", methods=["GET", "POST"])
# def register():
#     if request.method == "POST":
#         fullname = request.form["fullname"]
#         username = request.form["username"]
#         password = request.form["password"]
#         hashed_pw = generate_password_hash(password)

#         db = get_db()
#         try:
#             db.execute("INSERT INTO users (fullname, username, password) VALUES (?, ?, ?)",
#                        (fullname, username, hashed_pw))
#             db.commit()
#             return redirect("/login")
#         except sqlite3.IntegrityError:
#             return render_template("register.html", error="Email already exists.")
#     return render_template("register.html")

# # ---------- LOGIN ----------
# @app.route("/login", methods=["GET", "POST"])
# def login():
#     if request.method == "POST":
#         username = request.form["username"]
#         password = request.form["password"]

#         db = get_db()
#         user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

#         if user and check_password_hash(user["password"], password):
#             session["user"] = username
#             session["fullname"] = user["fullname"]
#             return redirect("/dashboard")
#         return render_template("login.html", error="Invalid credentials.")
#     return render_template("login.html")

# # ---------- DASHBOARD ----------
# @app.route("/dashboard")
# def dashboard():
#     if "user" in session:
#         return render_template("dashboard.html", fullname=session["fullname"])
#     return redirect("/login")

# # ---------- LOGOUT ----------
# @app.route("/logout")
# def logout():
#     session.clear()
#     return redirect("/login")

# # ---------- CHAT PAGE ----------
# @app.route("/chat")
# def chat_page():
#     if "user" in session:
#         return render_template("chat.html")
#     return redirect("/login")

# # ---------- CHAT FUNCTION ----------
# @app.route("/get", methods=["POST"])
# def chat():
#     if "user" not in session:
#         return "Unauthorized", 401

#     username = session["user"]
#     msg = request.form["msg"]
#     input_text = msg

#     # Get relevant context
#     retrieved_docs = retriever.invoke(input_text)
#     context = "\n\n".join([doc.page_content for doc in retrieved_docs])

#     system_prompt = (
#         "You are a helpful medical assistant. "
#         "Use the retrieved context below to answer concisely:\n\n" + context
#     )

#     completion = client.chat.completions.create(
#         model="gpt-3.5-turbo",
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": input_text}
#         ]
#     )

#     answer = completion.choices[0].message.content.strip()

#     # Save chat
#     db = get_db()
#     db.execute(
#         "INSERT INTO chat_history (username, question, answer, timestamp) VALUES (?, ?, ?, ?)",
#         (username, input_text, answer, datetime.now())
#     )
#     db.commit()

#     return answer

# # ---------- VIEW CHAT HISTORY ----------
# @app.route("/history")
# def history():
#     if "user" not in session:
#         return redirect("/login")

#     username = session["user"]
#     db = get_db()
#     rows = db.execute(
#         "SELECT id, question, answer, timestamp FROM chat_history WHERE username = ? ORDER BY timestamp DESC",
#         (username,)
#     ).fetchall()

#     history = [dict(row) for row in rows]
#     return render_template("history.html", history=history)

# # ---------- DELETE SPECIFIC CHAT ----------
# @app.route("/delete_chat/<int:chat_id>")
# def delete_chat(chat_id):
#     if "user" not in session:
#         return redirect("/login")

#     db = get_db()
#     db.execute("DELETE FROM chat_history WHERE id = ?", (chat_id,))
#     db.commit()
#     return redirect("/history")

# # ---------- DELETE ALL HISTORY ----------
# @app.route("/delete_all")
# def delete_all():
#     if "user" not in session:
#         return redirect("/login")

#     username = session["user"]
#     db = get_db()
#     db.execute("DELETE FROM chat_history WHERE username = ?", (username,))
#     db.commit()
#     return redirect("/history")
# # ---------- FORGOT PASSWORD ----------
# @app.route("/forgot", methods=["GET", "POST"])
# def forgot_password():
#     if request.method == "POST":
#         email = request.form["username"]
#         db = get_db()
#         user = db.execute("SELECT * FROM users WHERE username = ?", (email,)).fetchone()

#         if not user:
#             return render_template("forgot.html", error="Email not found.")

#         # Generate password reset token (valid for 1 hour)
#         token = serializer.dumps(email, salt="password-reset-salt")
#         reset_link = url_for("reset_password", token=token, _external=True)

#         # Send email
#         msg = Message("Password Reset Request", recipients=[email])
#         msg.body = f"Hello {user['fullname']},\n\nClick the link below to reset your password:\n{reset_link}\n\nThis link will expire in 1 hour."
#         mail.send(msg)

#         return render_template("forgot.html", success="Password reset link sent to your email.")
#     return render_template("forgot.html")


# # ---------- RESET PASSWORD ----------
# @app.route("/reset/<token>", methods=["GET", "POST"])
# def reset_password(token):
#     try:
#         email = serializer.loads(token, salt="password-reset-salt", max_age=3600)
#     except Exception:
#         return "The password reset link is invalid or has expired."

#     if request.method == "POST":
#         new_password = request.form["password"]
#         hashed_pw = generate_password_hash(new_password)
#         db = get_db()
#         db.execute("UPDATE users SET password = ? WHERE username = ?", (hashed_pw, email))
#         db.commit()
#         return redirect("/login")

#     return render_template("reset.html", email=email)

# # ---------- MAIN ----------
# if __name__ == "__main__":
#     init_db()
#     app.run(host="0.0.0.0", port=5000, debug=True)
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import sqlite3
from flask import Flask, render_template, request, redirect, session, url_for, g
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import PineconeVectorStore
from openai import OpenAI
from datetime import datetime

# ----------------- Initialize app and environment -----------------
app = Flask(__name__)
app.secret_key = "supersecretkey"
serializer = URLSafeTimedSerializer(app.secret_key)
load_dotenv()

# ----------------- Mail Config -----------------
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.environ.get("EMAIL_USER"),
    MAIL_PASSWORD=os.environ.get("EMAIL_PASS"),
    MAIL_DEFAULT_SENDER=os.environ.get("EMAIL_USER"),
    MAIL_DEBUG=True,
    MAIL_SUPPRESS_SEND=False
)
mail = Mail(app)

# ----------------- Database -----------------
DATABASE = "users.db"

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# Create tables if not exist
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        # Users table with fullname
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)

        # Chat history table with timestamps
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.commit()

# ----------------- AI and Pinecone setup -----------------
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY

embeddings = download_hugging_face_embeddings()
index_name = "medicalbot"
docsearch = PineconeVectorStore.from_existing_index(index_name=index_name, embedding=embeddings)
retriever = docsearch.as_retriever(search_type="similarity", search_kwargs={"k": 3})
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)

# ----------------- Routes -----------------

@app.route("/")
def index():
    return redirect("/login")

# ---------- REGISTER ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form["fullname"]
        username = request.form["username"]
        password = request.form["password"]
        hashed_pw = generate_password_hash(password)

        db = get_db()
        try:
            db.execute("INSERT INTO users (fullname, username, password) VALUES (?, ?, ?)",
                       (fullname, username, hashed_pw))
            db.commit()
            return redirect("/login")
        except sqlite3.IntegrityError:
            return render_template("register.html", error="Email already exists.")
    return render_template("register.html")

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user"] = username
            session["fullname"] = user["fullname"]
            return redirect("/dashboard")
        return render_template("login.html", error="Invalid credentials.")
    return render_template("login.html")

# ---------- DASHBOARD ----------
@app.route("/dashboard")
def dashboard():
    if "user" in session:
        return render_template("dashboard.html", fullname=session["fullname"])
    return redirect("/login")

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------- CHAT PAGE ----------
@app.route("/chat")
def chat_page():
    if "user" in session:
        return render_template("chat.html")
    return redirect("/login")

# ---------- CHAT FUNCTION ----------
@app.route("/get", methods=["POST"])
def chat():
    if "user" not in session:
        return "Unauthorized", 401

    username = session["user"]
    msg = request.form["msg"]
    input_text = msg

    # Get relevant context
    retrieved_docs = retriever.invoke(input_text)
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])

    system_prompt = (
        "You are a helpful medical assistant. "
        "Use the retrieved context below to answer concisely:\n\n" + context
    )

    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input_text}
        ]
    )

    answer = completion.choices[0].message.content.strip()

    # Save chat
    db = get_db()
    db.execute(
        "INSERT INTO chat_history (username, question, answer, timestamp) VALUES (?, ?, ?, ?)",
        (username, input_text, answer, datetime.now())
    )
    db.commit()

    return answer

# ---------- VIEW CHAT HISTORY ----------
@app.route("/history")
def history():
    if "user" not in session:
        return redirect("/login")

    username = session["user"]
    db = get_db()
    rows = db.execute(
        "SELECT id, question, answer, timestamp FROM chat_history WHERE username = ? ORDER BY timestamp DESC",
        (username,)
    ).fetchall()

    history = [dict(row) for row in rows]
    return render_template("history.html", history=history)

# ---------- DELETE SPECIFIC CHAT ----------
@app.route("/delete_chat/<int:chat_id>")
def delete_chat(chat_id):
    if "user" not in session:
        return redirect("/login")

    db = get_db()
    db.execute("DELETE FROM chat_history WHERE id = ?", (chat_id,))
    db.commit()
    return redirect("/history")

# ---------- DELETE ALL HISTORY ----------
@app.route("/delete_all")
def delete_all():
    if "user" not in session:
        return redirect("/login")

    username = session["user"]
    db = get_db()
    db.execute("DELETE FROM chat_history WHERE username = ?", (username,))
    db.commit()
    return redirect("/history")

# ---------- FORGOT PASSWORD ----------
@app.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["username"]
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (email,)).fetchone()

        if not user:
            return render_template("forgot.html", error="Email not found.")

        # Generate password reset token (valid for 1 hour)
        token = serializer.dumps(email, salt="password-reset-salt")
        reset_link = url_for("reset_password", token=token, _external=True)

        # Send email with proper sender
        msg = Message(
            "Password Reset Request",
            sender=app.config["MAIL_DEFAULT_SENDER"],
            recipients=[email]
        )
        msg.body = f"""
Hello {user['fullname']},

Click the link below to reset your password:
{reset_link}

This link will expire in 1 hour.

Best regards,
MediBot Team
"""
        mail.send(msg)

        return render_template("forgot.html", success="Password reset link sent to your email.")
    return render_template("forgot.html")

# ---------- RESET PASSWORD ----------
@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = serializer.loads(token, salt="password-reset-salt", max_age=3600)
    except Exception:
        return "The password reset link is invalid or has expired."

    if request.method == "POST":
        new_password = request.form["password"]
        hashed_pw = generate_password_hash(new_password)
        db = get_db()
        db.execute("UPDATE users SET password = ? WHERE username = ?", (hashed_pw, email))
        db.commit()
        return redirect("/login")

    return render_template("reset.html", email=email)

# ---------- MAIN ----------
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)