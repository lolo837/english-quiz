import os, json, random, sqlite3, secrets
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "quiz.db")
QUESTIONS_PATH = os.path.join(BASE, "data", "questions.json")
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
EXAM_CODE = os.environ.get("EXAM_CODE", "CHANGE-THIS-CODE")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "CHANGE-THIS-ADMIN-PASSWORD")
ADMIN_NAME = os.environ.get("ADMIN_NAME", "Noor")

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            student_ref TEXT,
            started_at TEXT NOT NULL,
            submitted_at TEXT,
            question_order TEXT NOT NULL,
            answers TEXT NOT NULL DEFAULT '{}',
            score INTEGER,
            total INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'in_progress'
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS answer_key (
            question_id INTEGER PRIMARY KEY,
            correct_label TEXT
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        )""")
        con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('exam_active','1')")

def load_questions():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        return json.load(f)

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapped

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        name = request.form.get("student_name", "").strip()
        ref = request.form.get("student_ref", "").strip()
        code = request.form.get("exam_code", "").strip()
        if not name or code != EXAM_CODE:
            flash("تأكدي من الاسم وكود الامتحان.", "error")
            return redirect(url_for("home"))
        with db() as con:
            active = con.execute("SELECT value FROM settings WHERE key='exam_active'").fetchone()
            if not active or active["value"] != "1":
                flash("الامتحان غير متاح حالياً.", "error")
                return redirect(url_for("home"))
            qs = load_questions()
            order = list(range(1, len(qs)+1))
            random.shuffle(order)
            cur = con.execute("""INSERT INTO attempts(student_name,student_ref,started_at,question_order,answers,total)
                VALUES(?,?,?,?,?,?)""", (name, ref, datetime.now().isoformat(timespec="seconds"), json.dumps(order), "{}", len(qs)))
            attempt_id = cur.lastrowid
        session.clear()
        session["attempt_id"] = attempt_id
        return redirect(url_for("exam"))
    return render_template("home.html")

@app.route("/exam")
def exam():
    aid = session.get("attempt_id")
    if not aid: return redirect(url_for("home"))
    with db() as con:
        attempt = con.execute("SELECT * FROM attempts WHERE id=?", (aid,)).fetchone()
    if not attempt or attempt["status"] != "in_progress":
        return redirect(url_for("home"))
    all_qs = {q["id"]: q for q in load_questions()}
    order = json.loads(attempt["question_order"])
    qs = [all_qs[i] for i in order]
    # Correct answers are never sent to the student browser.
    public_qs = [{"id": q["id"], "question": q["question"], "options": q["options"]} for q in qs]
    return render_template("exam.html", questions=public_qs, student=attempt["student_name"])

@app.route("/submit", methods=["POST"])
def submit():
    aid = session.get("attempt_id")
    if not aid: return redirect(url_for("home"))
    payload = request.get_json(silent=True) or {}
    submitted = payload.get("answers", {})
    with db() as con:
        attempt = con.execute("SELECT * FROM attempts WHERE id=?", (aid,)).fetchone()
        if not attempt or attempt["status"] != "in_progress":
            return jsonify({"ok": False, "error": "تم تسليم الامتحان مسبقاً."}), 400
        allowed = {str(i) for i in json.loads(attempt["question_order"])}
        clean = {str(k): str(v) for k,v in submitted.items() if str(k) in allowed and v in ["A","B","C","D"]}
        key = {str(r["question_id"]): r["correct_label"] for r in con.execute("SELECT question_id,correct_label FROM answer_key").fetchall() if r["correct_label"]}
        # If the key has not been configured, refuse submission rather than silently issue a false score.
        if len(key) != attempt["total"]:
            return jsonify({"ok": False, "error": "لم يتم إعداد مفتاح الإجابات بالكامل بعد. تواصلي مع الإدارة."}), 400
        score = sum(1 for qid, ans in clean.items() if key.get(qid) == ans)
        con.execute("""UPDATE attempts SET answers=?,score=?,submitted_at=?,status='submitted' WHERE id=?""",
                    (json.dumps(clean), score, datetime.now().isoformat(timespec="seconds"), aid))
    session.clear()
    return jsonify({"ok": True, "message": "تم تسليم إجاباتك بنجاح. لن تظهر العلامة على شاشة الطالب."})

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if check_password_hash(generate_password_hash(ADMIN_PASSWORD), pw) if False else secrets.compare_digest(pw, ADMIN_PASSWORD):
            session["is_admin"] = True
            return redirect(url_for("dashboard"))
        flash("كلمة مرور الإدارة غير صحيحة.", "error")
    return render_template("admin_login.html", admin_name=ADMIN_NAME)

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("home"))

@app.route("/admin/dashboard")
@admin_required
def dashboard():
    with db() as con:
        attempts = con.execute("SELECT * FROM attempts ORDER BY id DESC").fetchall()
        key_rows = con.execute("SELECT * FROM answer_key").fetchall()
        active = con.execute("SELECT value FROM settings WHERE key='exam_active'").fetchone()
    qs = load_questions()
    key = {r["question_id"]: r["correct_label"] for r in key_rows}
    return render_template("dashboard.html", admin_name=ADMIN_NAME, attempts=attempts, questions=qs, key=key,
                           active=(active["value"] == "1" if active else True))

@app.route("/admin/key", methods=["POST"])
@admin_required
def save_key():
    data = request.form
    qs = load_questions()
    with db() as con:
        for q in qs:
            val = data.get(f"q{q['id']}", "")
            valid = {o["label"] for o in q["options"]}
            if val in valid:
                con.execute("INSERT INTO answer_key(question_id,correct_label) VALUES(?,?) ON CONFLICT(question_id) DO UPDATE SET correct_label=excluded.correct_label",
                            (q["id"], val))
            else:
                con.execute("DELETE FROM answer_key WHERE question_id=?", (q["id"],))
    flash("تم حفظ مفتاح الإجابات.", "success")
    return redirect(url_for("dashboard"))

@app.route("/admin/toggle", methods=["POST"])
@admin_required
def toggle():
    val = "1" if request.form.get("active") == "1" else "0"
    with db() as con:
        con.execute("UPDATE settings SET value=? WHERE key='exam_active'", (val,))
    return redirect(url_for("dashboard"))

@app.route("/admin/attempt/<int:aid>")
@admin_required
def attempt_detail(aid):
    with db() as con:
        a = con.execute("SELECT * FROM attempts WHERE id=?", (aid,)).fetchone()
        key = {r["question_id"]:r["correct_label"] for r in con.execute("SELECT * FROM answer_key")}
    if not a: abort(404)
    qs = {q["id"]:q for q in load_questions()}
    answers = json.loads(a["answers"])
    order = json.loads(a["question_order"])
    details = []
    for qid in order:
        q = qs[qid]
        details.append({"q":q, "answer":answers.get(str(qid)), "correct":key.get(qid)})
    return render_template("attempt.html", attempt=a, details=details)

@app.route("/health")
def health():
    return {"status":"ok"}

init_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
