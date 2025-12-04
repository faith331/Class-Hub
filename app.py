
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, datetime

APP_NAME = "ClassHub"
DB_PATH = os.path.join(os.path.dirname(__file__), "classhub.db")

def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        db = g._db = sqlite3.connect(DB_PATH, check_same_thread=False)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT CHECK(role IN ('teacher','student')) NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL,
        created_by INTEGER,
        FOREIGN KEY(created_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        due_date TEXT,
        created_at TEXT NOT NULL,
        created_by INTEGER,
        FOREIGN KEY(created_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        content TEXT,
        submitted_at TEXT NOT NULL,
        score REAL,
        feedback TEXT,
        UNIQUE(assignment_id, student_id),
        FOREIGN KEY(assignment_id) REFERENCES assignments(id),
        FOREIGN KEY(student_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS discussions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        created_at TEXT NOT NULL,
        created_by INTEGER,
        FOREIGN KEY(created_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS discussion_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discussion_id INTEGER NOT NULL,
        author_id INTEGER NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(discussion_id) REFERENCES discussions(id),
        FOREIGN KEY(author_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        created_by INTEGER,
        FOREIGN KEY(created_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS quiz_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER NOT NULL,
        prompt TEXT NOT NULL,
        choice_a TEXT NOT NULL,
        choice_b TEXT NOT NULL,
        choice_c TEXT NOT NULL,
        choice_d TEXT NOT NULL,
        correct TEXT CHECK(correct IN ('A','B','C','D')) NOT NULL,
        FOREIGN KEY(quiz_id) REFERENCES quizzes(id)
    );

    CREATE TABLE IF NOT EXISTS quiz_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        submitted_at TEXT NOT NULL,
        score REAL DEFAULT 0,
        UNIQUE(quiz_id, student_id),
        FOREIGN KEY(quiz_id) REFERENCES quizzes(id),
        FOREIGN KEY(student_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS quiz_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        answer TEXT CHECK(answer IN ('A','B','C','D')),
        FOREIGN KEY(response_id) REFERENCES quiz_responses(id),
        FOREIGN KEY(question_id) REFERENCES quiz_questions(id)
    );
    """)
    db.commit()

def seed_demo():
    db = get_db()
    # Seed a teacher and student if none
    if db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"] == 0:
        now = datetime.datetime.utcnow().isoformat()
        db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES (?,?,?,?,?)",
                   ("Teacher Demo","teacher@classhub.local", generate_password_hash("password123"), "teacher", now))
        db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES (?,?,?,?,?)",
                   ("Student Demo","student@classhub.local", generate_password_hash("password123"), "student", now))
        db.commit()
    # Seed content
    if db.execute("SELECT COUNT(*) AS c FROM announcements").fetchone()["c"] == 0:
        tid = db.execute("SELECT id FROM users WHERE role='teacher' LIMIT 1").fetchone()["id"]
        now = datetime.datetime.utcnow().isoformat()
        db.execute("INSERT INTO announcements(title,body,created_at,created_by) VALUES (?,?,?,?)",
                   ("Welcome to ClassHub","Explore assignments, discussions, and quizzes.", now, tid))
        db.execute("INSERT INTO assignments(title,description,due_date,created_at,created_by) VALUES (?,?,?,?,?)",
                   ("Sample Assignment","Submit a paragraph or a link.", (datetime.date.today()+datetime.timedelta(days=7)).isoformat(), now, tid))
        db.execute("INSERT INTO discussions(topic, created_at, created_by) VALUES (?,?,?)",
                   ("Introduce yourself", now, tid))
        db.execute("INSERT INTO quizzes(title, created_at, created_by) VALUES (?,?,?)",
                   ("Orientation Quiz", now, tid))
        qid = db.execute("SELECT id FROM quizzes ORDER BY id DESC LIMIT 1").fetchone()["id"]
        qs = [("ClassHub is?", "Bank", "Course hub", "Game", "Shop", "B"),
              ("Who posts assignments?", "Parents","Students","Teachers","Guests","C"),
              ("Theme colors are?", "Orange/White","Green/Black","Purple/Gold","Blue/Gray","A")]
        for p,a,b,c,d,ans in qs:
            db.execute("""INSERT INTO quiz_questions(quiz_id,prompt,choice_a,choice_b,choice_c,choice_d,correct)
                          VALUES (?,?,?,?,?,?,?)""", (qid,p,a,b,c,d,ans))
        db.commit()

app = Flask(__name__)
app.secret_key = os.environ.get("CLASSHUB_SECRET","dev-secret")

@app.before_request
def _pre():
    init_db()

@app.teardown_appcontext
def _close(exc):
    db = getattr(g, "_db", None)
    if db is not None:
        db.close()

# ----------------- Auth -----------------
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        role = request.form.get("role")
        if not name or not email or not pw or role not in ("teacher","student"):
            flash("Fill all fields correctly.", "danger")
            return redirect(url_for("register"))
        db = get_db()
        try:
            db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES (?,?,?,?,?)",
                       (name, email, generate_password_hash(pw), role, datetime.datetime.utcnow().isoformat()))
            db.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered.", "warning")
            return redirect(url_for("register"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], pw):
            session["user"] = {"id": user["id"], "name": user["name"], "role": user["role"], "email": user["email"]}
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.", "danger")
        return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out.", "info")
    return redirect(url_for("index"))

# ----------------- Core Pages -----------------
@app.route("/")
def index():
    db = get_db()
    ann = db.execute("SELECT * FROM announcements ORDER BY created_at DESC LIMIT 4").fetchall()
    return render_template("home.html", announcements=ann)

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    db = get_db()
    # counts
    ann = db.execute("SELECT COUNT(*) c FROM announcements").fetchone()["c"]
    asg = db.execute("SELECT COUNT(*) c FROM assignments").fetchone()["c"]
    qz = db.execute("SELECT COUNT(*) c FROM quizzes").fetchone()["c"]
    avg = None
    if session["user"]["role"] == "student":
        avg = db.execute("SELECT AVG(score) a FROM submissions WHERE student_id=?", (session["user"]["id"],)).fetchone()["a"]
    return render_template("dashboard.html", ann_count=ann, asg_count=asg, quiz_count=qz, avg_grade=avg)

# ---------- Announcements ----------
@app.route("/announcements")
def announcements():
    db = get_db()
    rows = db.execute("SELECT a.*, u.name AS author FROM announcements a LEFT JOIN users u ON a.created_by=u.id ORDER BY created_at DESC").fetchall()
    return render_template("announcements.html", rows=rows)

@app.route("/announcements/new", methods=["GET","POST"])
def announcement_new():
    if "user" not in session or session["user"]["role"]!="teacher":
        flash("Teacher login required.", "warning"); return redirect(url_for("login"))
    if request.method == "POST":
        db = get_db()
        db.execute("INSERT INTO announcements(title,body,created_at,created_by) VALUES (?,?,?,?)",
                   (request.form.get("title") or "Untitled",
                    request.form.get("body") or "",
                    datetime.datetime.utcnow().isoformat(),
                    session["user"]["id"]))
        db.commit()
        flash("Announcement posted.", "success")
        return redirect(url_for("announcements"))
    return render_template("announcement_form.html")

# ---------- Assignments ----------
@app.route("/assignments")
def assignments():
    db = get_db()
    rows = db.execute("SELECT a.*, u.name AS author FROM assignments a LEFT JOIN users u ON a.created_by=u.id ORDER BY created_at DESC").fetchall()
    return render_template("assignments.html", rows=rows)

@app.route("/assignments/new", methods=["GET","POST"])
def assignment_new():
    if "user" not in session or session["user"]["role"]!="teacher":
        flash("Teacher login required.", "warning"); return redirect(url_for("login"))
    if request.method == "POST":
        db = get_db()
        db.execute("INSERT INTO assignments(title,description,due_date,created_at,created_by) VALUES (?,?,?,?,?)",
                   (request.form.get("title") or "Untitled",
                    request.form.get("description") or "",
                    request.form.get("due_date") or None,
                    datetime.datetime.utcnow().isoformat(),
                    session["user"]["id"]))
        db.commit()
        flash("Assignment created successfully.", "success")
        return redirect(url_for("assignments"))
    return render_template("assignment_form.html")

@app.route("/assignments/<int:aid>", methods=["GET","POST"])
def assignment_detail(aid):
    db = get_db()
    a = db.execute("SELECT * FROM assignments WHERE id=?", (aid,)).fetchone()
    if not a:
        flash("Assignment not found.", "warning"); return redirect(url_for("assignments"))
    submission = None
    if "user" in session and session["user"]["role"]=="student":
        submission = db.execute("SELECT * FROM submissions WHERE assignment_id=? AND student_id=?", (aid, session["user"]["id"])).fetchone()
        if request.method == "POST":
            content = request.form.get("content") or ""
            now = datetime.datetime.utcnow().isoformat()
            ex = db.execute("SELECT id FROM submissions WHERE assignment_id=? AND student_id=?", (aid, session["user"]["id"])).fetchone()
            if ex:
                db.execute("UPDATE submissions SET content=?, submitted_at=? WHERE id=?", (content, now, ex["id"]))
            else:
                db.execute("INSERT INTO submissions(assignment_id,student_id,content,submitted_at) VALUES (?,?,?,?)",
                           (aid, session["user"]["id"], content, now))
            db.commit(); flash("Submission saved.", "success")
            return redirect(url_for("assignment_detail", aid=aid))

    subs = []
    if "user" in session and session["user"]["role"]=="teacher":
        subs = db.execute("""SELECT s.*, u.name AS student_name FROM submissions s
                             LEFT JOIN users u ON u.id=s.student_id
                             WHERE s.assignment_id=? ORDER BY submitted_at DESC""", (aid,)).fetchall()
        if request.method == "POST":
            sid = request.form.get("sid"); score = request.form.get("score"); feedback = request.form.get("feedback")
            if sid:
                db.execute("UPDATE submissions SET score=?, feedback=? WHERE id=?", (score, feedback, sid))
                db.commit(); flash("Graded.", "success")
                return redirect(url_for("assignment_detail", aid=aid))

    return render_template("assignment_detail.html", a=a, submission=submission, subs=subs)

# ---------- Discussions ----------
@app.route("/discussions")
def discussions():
    db = get_db()
    rows = db.execute("SELECT d.*, u.name AS author FROM discussions d LEFT JOIN users u ON d.created_by=u.id ORDER BY created_at DESC").fetchall()
    return render_template("discussions.html", rows=rows)

@app.route("/discussions/new", methods=["GET","POST"])
def discussion_new():
    if "user" not in session or session["user"]["role"]!="teacher":
        flash("Teacher login required.", "warning"); return redirect(url_for("login"))
    if request.method == "POST":
        db = get_db()
        db.execute("INSERT INTO discussions(topic, created_at, created_by) VALUES (?,?,?)",
                   (request.form.get("topic") or "Untitled", datetime.datetime.utcnow().isoformat(), session["user"]["id"]))
        db.commit(); flash("Discussion created.", "success")
        return redirect(url_for("discussions"))
    return render_template("discussion_form.html")

@app.route("/discussions/<int:did>", methods=["GET","POST"])
def discussion_detail(did):
    db = get_db()
    d = db.execute("SELECT * FROM discussions WHERE id=?", (did,)).fetchone()
    if not d: flash("Discussion not found.","warning"); return redirect(url_for("discussions"))
    posts = db.execute("""SELECT p.*, u.name AS author FROM discussion_posts p
                          LEFT JOIN users u ON u.id=p.author_id
                          WHERE p.discussion_id=? ORDER BY created_at ASC""", (did,)).fetchall()
    if request.method == "POST":
        if "user" not in session:
            flash("Login first.", "warning"); return redirect(url_for("login"))
        body = request.form.get("body") or ""
        db.execute("INSERT INTO discussion_posts(discussion_id,author_id,body,created_at) VALUES (?,?,?,?)",
                   (did, session["user"]["id"], body, datetime.datetime.utcnow().isoformat()))
        db.commit(); return redirect(url_for("discussion_detail", did=did))
    return render_template("discussion_detail.html", d=d, posts=posts)

# ---------- Quizzes ----------
@app.route("/quizzes")
def quizzes():
    db = get_db()
    rows = db.execute("SELECT q.*, u.name AS author FROM quizzes q LEFT JOIN users u ON q.created_by=u.id ORDER BY created_at DESC").fetchall()
    return render_template("quizzes.html", rows=rows)

@app.route("/quizzes/new", methods=["GET","POST"])
def quiz_new():
    if "user" not in session or session["user"]["role"]!="teacher":
        flash("Teacher login required.", "warning"); return redirect(url_for("login"))
    db = get_db()
    if request.method == "POST":
        title = request.form.get("title") or "Untitled Quiz"
        now = datetime.datetime.utcnow().isoformat()
        db.execute("INSERT INTO quizzes(title, created_at, created_by) VALUES (?,?,?)", (title, now, session["user"]["id"]))
        db.commit()
        quiz_id = db.execute("SELECT id FROM quizzes ORDER BY id DESC LIMIT 1").fetchone()["id"]
        for i in range(1,6):
            prompt = request.form.get(f"q{i}_prompt")
            a = request.form.get(f"q{i}_a"); b = request.form.get(f"q{i}_b"); c = request.form.get(f"q{i}_c"); d = request.form.get(f"q{i}_d")
            correct = request.form.get(f"q{i}_correct")
            if prompt and a and b and c and d and correct in ("A","B","C","D"):
                db.execute("""INSERT INTO quiz_questions(quiz_id,prompt,choice_a,choice_b,choice_c,choice_d,correct)
                              VALUES (?,?,?,?,?,?,?)""",(quiz_id,prompt,a,b,c,d,correct))
        db.commit(); flash("Quiz created.","success")
        return redirect(url_for("quizzes"))
    return render_template("quiz_form.html")

@app.route("/quizzes/<int:qid>", methods=["GET","POST"])
def quiz_take(qid):
    db = get_db()
    quiz = db.execute("SELECT * FROM quizzes WHERE id=?", (qid,)).fetchone()
    if not quiz: flash("Quiz not found.","warning"); return redirect(url_for("quizzes"))
    questions = db.execute("SELECT * FROM quiz_questions WHERE quiz_id=?", (qid,)).fetchall()
    if request.method == "POST":
        if "user" not in session or session["user"]["role"]!="student":
            flash("Student login required.","warning"); return redirect(url_for("login"))
        ex = db.execute("SELECT id FROM quiz_responses WHERE quiz_id=? AND student_id=?", (qid, session["user"]["id"])).fetchone()
        if ex: flash("You already submitted this quiz.","info"); return redirect(url_for("quiz_take", qid=qid))
        now = datetime.datetime.utcnow().isoformat()
        db.execute("INSERT INTO quiz_responses(quiz_id,student_id,submitted_at) VALUES (?,?,?)",(qid,session["user"]["id"],now))
        resp_id = db.execute("SELECT id FROM quiz_responses WHERE quiz_id=? AND student_id=?", (qid, session["user"]["id"])).fetchone()["id"]
        score = 0.0
        for q in questions:
            ans = request.form.get(f"q{q['id']}")
            db.execute("INSERT INTO quiz_answers(response_id,question_id,answer) VALUES (?,?,?)",(resp_id,q["id"],ans))
            if ans == q["correct"]: score += 1.0
        total = len(questions) or 1
        pct = (score/total)*100.0
        db.execute("UPDATE quiz_responses SET score=? WHERE id=?", (pct, resp_id)); db.commit()
        flash(f"Quiz submitted. Score: {pct:.0f}%","success"); return redirect(url_for("quizzes"))
    results = []
    if "user" in session and session["user"]["role"]=="teacher":
        results = db.execute("""SELECT r.*, u.name AS student_name FROM quiz_responses r
                                LEFT JOIN users u ON u.id=r.student_id
                                WHERE r.quiz_id=? ORDER BY submitted_at DESC""",(qid,)).fetchall()
    return render_template("quiz_take.html", quiz=quiz, questions=questions, results=results)

@app.context_processor
def inject_ctx():
    return {"now": datetime.datetime.utcnow(), "current_user": session.get("user")}

if __name__ == "__main__":
    with app.app_context():
        init_db(); seed_demo()
    app.run(debug=True)
