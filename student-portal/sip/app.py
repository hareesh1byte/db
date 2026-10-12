import os
import datetime
import decimal
from functools import wraps

import mysql.connector
from flask import Flask, request, jsonify, session, render_template
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-this-secret")

# In Codespaces, MySQL must be running in the same Codespace for 127.0.0.1
# to work. For a hosted database, set DB_HOST to its hostname.
DB = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "webuser"),
    "password": os.getenv("DB_PASSWORD", os.getenv("DB_PASS", "")),
    "database": os.getenv("DB_NAME", "sip"),
    "connection_timeout": 5,
}

def clean(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()[:10]
    if isinstance(value, decimal.Decimal):
        return float(value)
    return value

def q(sql, args=(), one=False, write=False):
    conn = mysql.connector.connect(**DB)
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, args)
        if write:
            conn.commit()
            return cur.lastrowid
        rows = [{key: clean(value) for key, value in row.items()}
                for row in cur.fetchall()]
        return (rows[0] if rows else None) if one else rows
    finally:
        cur.close()
        conn.close()

def auth(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "uid" not in session:
            return jsonify(error="Please sign in"), 401
        return func(*args, **kwargs)
    return wrapper

@app.errorhandler(mysql.connector.Error)
def db_err(error):
    app.logger.exception("Database error")
    if getattr(error, "errno", None) == 1062:
        message = "That roll number or value already exists."
    elif getattr(error, "errno", None) in (2003, 2005):
        message = ("Cannot reach MySQL. Check that MySQL is running and "
                   "DB_HOST/DB_PORT are correct.")
    elif getattr(error, "errno", None) == 1045:
        message = "MySQL rejected the credentials. Check DB_USER and DB_PASSWORD."
    elif getattr(error, "errno", None) == 1049:
        message = "Database 'sip' does not exist. Run schema.sql first."
    else:
        message = "Database request failed. Check the Codespaces terminal for details."
    return jsonify(error=message), 500

@app.route("/")
def index():
    return render_template("index.html")

@app.get("/api/health")
def health():
    try:
        q("SELECT 1 AS ok", one=True)
        return jsonify(status="ok", database="connected")
    except mysql.connector.Error:
        return jsonify(status="error", database="unavailable",
                       hint="Start MySQL, import schema.sql, and check DB_* settings."), 503

@app.post("/api/login")
def login():
    data = request.json or {}
    user = q("SELECT * FROM users WHERE username=%s",
             (data.get("username"),), one=True)
    if not user or not check_password_hash(
        user["password_hash"], data.get("password", "")
    ):
        return jsonify(error="Wrong username or password"), 401
    session["uid"] = user["id"]
    session["user"] = user["username"]
    return jsonify(user=user["username"])

@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)

@app.get("/api/me")
@auth
def me():
    return jsonify(user=session["user"])

STUDENT_FIELDS = ["roll_no", "name", "email", "phone", "class_name", "dob"]

def student_values(data):
    return [data.get(key) or None for key in STUDENT_FIELDS]

@app.get("/api/students")
@auth
def students():
    return jsonify(q("SELECT * FROM students ORDER BY roll_no"))

@app.post("/api/students")
@auth
def add_student():
    q("INSERT INTO students(roll_no,name,email,phone,class_name,dob) "
      "VALUES(%s,%s,%s,%s,%s,%s)", student_values(request.json or {}), write=True)
    return jsonify(ok=True)

@app.put("/api/students/<int:student_id>")
@auth
def edit_student(student_id):
    q("UPDATE students SET roll_no=%s,name=%s,email=%s,phone=%s,"
      "class_name=%s,dob=%s WHERE id=%s",
      student_values(request.json or {}) + [student_id], write=True)
    return jsonify(ok=True)

@app.delete("/api/students/<int:student_id>")
@auth
def delete_student(student_id):
    q("DELETE FROM students WHERE id=%s", (student_id,), write=True)
    return jsonify(ok=True)

@app.get("/api/subjects")
@auth
def subjects():
    return jsonify(q("SELECT * FROM subjects ORDER BY name"))

@app.get("/api/attendance")
@auth
def get_attendance():
    date = request.args.get("date", datetime.date.today().isoformat())
    return jsonify(q(
        "SELECT s.id,s.roll_no,s.name,a.status FROM students s "
        "LEFT JOIN attendance a ON a.student_id=s.id AND a.att_date=%s "
        "ORDER BY s.roll_no", (date,)
    ))

@app.post("/api/attendance")
@auth
def save_attendance():
    data = request.json or {}
    for record in data.get("records", []):
        if record.get("status"):
            q("INSERT INTO attendance(student_id,att_date,status) "
              "VALUES(%s,%s,%s) ON DUPLICATE KEY UPDATE status=VALUES(status)",
              (record["student_id"], data["date"], record["status"]), write=True)
    return jsonify(ok=True)

@app.get("/api/grades")
@auth
def get_grades():
    student_id = request.args.get("student_id")
    sql = ("SELECT g.*,s.name student,s.roll_no,sub.name subject,"
           "ROUND(g.marks/g.max_marks*100,1) pct FROM grades g "
           "JOIN students s ON s.id=g.student_id "
           "JOIN subjects sub ON sub.id=g.subject_id")
    if student_id:
        return jsonify(q(sql + " WHERE g.student_id=%s ORDER BY g.id DESC",
                         (student_id,)))
    return jsonify(q(sql + " ORDER BY g.id DESC LIMIT 200"))

@app.post("/api/grades")
@auth
def add_grade():
    data = request.json or {}
    q("INSERT INTO grades(student_id,subject_id,exam,marks,max_marks) "
      "VALUES(%s,%s,%s,%s,%s)",
      (data["student_id"], data["subject_id"], data["exam"],
       data["marks"], data.get("max_marks") or 100), write=True)
    return jsonify(ok=True)

@app.delete("/api/grades/<int:grade_id>")
@auth
def delete_grade(grade_id):
    q("DELETE FROM grades WHERE id=%s", (grade_id,), write=True)
    return jsonify(ok=True)

@app.get("/api/stats")
@auth
def stats():
    today = datetime.date.today().isoformat()
    return jsonify(
        students=q("SELECT COUNT(*) n FROM students", one=True)["n"],
        present_today=q("SELECT COUNT(*) n FROM attendance "
                        "WHERE att_date=%s AND status IN('Present','Late')",
                        (today,), one=True)["n"],
        attendance_rate=q("SELECT ROUND(100*AVG(status<>'Absent'),1) n "
                          "FROM attendance", one=True)["n"],
        avg_grade=q("SELECT ROUND(AVG(marks/max_marks*100),1) n "
                    "FROM grades", one=True)["n"],
        top=q("SELECT s.name,ROUND(AVG(g.marks/g.max_marks*100),1) pct "
              "FROM grades g JOIN students s ON s.id=g.student_id "
              "GROUP BY s.id ORDER BY pct DESC LIMIT 5")
    )

def initialize_admin():
    # Run only after schema.sql has been imported.
    if not q("SELECT id FROM users WHERE username=%s", ("admin",), one=True):
        q("INSERT INTO users(username,password_hash) VALUES(%s,%s)",
          ("admin", generate_password_hash(
              os.getenv("ADMIN_PASSWORD", "admin123")
          )), write=True)

if __name__ == "__main__":
    try:
        initialize_admin()
    except mysql.connector.Error as error:
        raise SystemExit(
            "Cannot initialize the app database. Start MySQL, import schema.sql, "
            "and set DB_HOST, DB_USER, DB_PASSWORD, and DB_NAME. "
            f"MySQL said: {error}"
        )
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
