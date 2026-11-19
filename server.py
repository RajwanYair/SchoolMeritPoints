#!/usr/intel/bin/python3
"""SchoolMeritPoints — School Merit Points Web Application.

Python stdlib HTTP server + SQLite, no external dependencies.
3-tier RBAC: admin, teacher, student. Single-file PWA.

Usage: python3 server.py [--port 8080] [--db points.db]
"""

import argparse
import csv
import hashlib
import hmac
import http.server
import io
import json
import os
import secrets
import sqlite3
import sys
import threading
import time
import urllib.parse
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_DEFAULT = str(APP_DIR / "points.db")
SECRET = os.environ.get("POINTS_SECRET") or secrets.token_hex(32)
PUBLIC_STATIC_FILES = {"index.html", "spec.html", "manifest.webmanifest", "icon.svg"}

# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_DEFAULT, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        role        TEXT NOT NULL CHECK(role IN ('admin','teacher','student')),
        username    TEXT UNIQUE NOT NULL,
        password    TEXT NOT NULL,
        barcode     TEXT UNIQUE,
        active      INTEGER NOT NULL DEFAULT 1,
        pin         TEXT
    );
    CREATE TABLE IF NOT EXISTS classes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL UNIQUE,
        grade       TEXT,
        teacher_id  INTEGER REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS class_members (
        student_id  INTEGER REFERENCES users(id),
        class_id    INTEGER REFERENCES classes(id),
        year        TEXT NOT NULL,
        PRIMARY KEY (student_id, class_id, year)
    );
    CREATE TABLE IF NOT EXISTS criteria (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        kind        TEXT NOT NULL CHECK(kind IN ('personal','class')),
        add_value   INTEGER NOT NULL DEFAULT 1,
        sub_value   INTEGER NOT NULL DEFAULT 1,
        daily_limit INTEGER DEFAULT 1,
        active      INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS entries (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        target_type TEXT NOT NULL CHECK(target_type IN ('student','class')),
        target_id   INTEGER NOT NULL,
        criterion_id INTEGER REFERENCES criteria(id),
        delta       INTEGER NOT NULL,
        teacher_id  INTEGER REFERENCES users(id),
        note        TEXT,
        ts          TEXT NOT NULL DEFAULT (datetime('now')),
        cancelled   INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS periods (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        start_date  TEXT NOT NULL,
        end_date    TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_entries_target ON entries(target_type, target_id);
    CREATE INDEX IF NOT EXISTS idx_entries_ts      ON entries(ts);
    CREATE INDEX IF NOT EXISTS idx_users_role       ON users(role);
    """)
    # Seed default admin if none exist
    cur = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    if cur.fetchone()[0] == 0:
        pw = hash_password("admin123")
        conn.execute(
            "INSERT INTO users (name, role, username, password) VALUES (?,?,?,?)",
            ("מנהל מערכת", "admin", "admin", pw),
        )
    # Seed default criteria if empty
    cur = conn.execute("SELECT COUNT(*) FROM criteria")
    if cur.fetchone()[0] == 0:
        defaults = [
            ("תלבושת", "personal", 2, 1, 1),
            ("ציצית", "personal", 2, 1, 1),
            ("הגעה בזמן", "personal", 3, 2, 1),
            ("מבצע חל\"ל", "personal", 5, 0, 0),
            ("התנהגות בדרך ארץ", "personal", 5, 3, 0),
            ("סדר וניקיון הכיתה", "class", 5, 3, 1),
            ("קירות נקיים", "class", 3, 3, 0),
            ("כיתה מקושטת", "class", 10, 0, 0),
            ("הרמת כיסאות בסוף היום", "class", 2, 2, 1),
            ("תורנים כיתתיים", "class", 3, 2, 1),
            ("כוורות מסודרות", "class", 3, 2, 0),
        ]
        conn.executemany(
            "INSERT INTO criteria (name,kind,add_value,sub_value,daily_limit) VALUES (?,?,?,?,?)",
            defaults,
        )
    # Seed demo teachers, classes, students, and sample entries if classes table is empty
    cur = conn.execute("SELECT COUNT(*) FROM classes")
    if cur.fetchone()[0] == 0:
        t1_cur = conn.execute(
            "INSERT INTO users (name, role, username, password) VALUES (?,?,?,?)",
            ("הרב דוד לוי", "teacher", "david", hash_password("teacher123")),
        )
        t1_id = t1_cur.lastrowid
        t2_cur = conn.execute(
            "INSERT INTO users (name, role, username, password) VALUES (?,?,?,?)",
            ("הרב משה כהן", "teacher", "moshe", hash_password("teacher123")),
        )
        t2_id = t2_cur.lastrowid

        c1_id = conn.execute(
            "INSERT INTO classes (name, grade, teacher_id) VALUES (?,?,?)",
            ("ו'1", "ו", t1_id),
        ).lastrowid
        c2_id = conn.execute(
            "INSERT INTO classes (name, grade, teacher_id) VALUES (?,?,?)",
            ("ו'2", "ו", t2_id),
        ).lastrowid
        c3_id = conn.execute(
            "INSERT INTO classes (name, grade, teacher_id) VALUES (?,?,?)",
            ("ז'1", "ז", t1_id),
        ).lastrowid

        year_str = str(time.localtime().tm_year)
        demo_students = [
            ("נועם כהן", "noam", c1_id),
            ("אורי לוי", "uri", c1_id),
            ("איתי מזרחי", "itai", c1_id),
            ("יונתן אברהם", "yonatan", c1_id),
            ("דניאל פרץ", "daniel", c2_id),
            ("אייל חדד", "eyal", c2_id),
            ("עמית ביטון", "amit", c2_id),
            ("שחר גבאי", "shachar", c3_id),
            ("עידו שפירא", "ido", c3_id),
            ("נדב כץ", "nadav", c3_id),
        ]
        student_ids = {}
        for s_name, s_user, s_cid in demo_students:
            scur = conn.execute(
                "INSERT INTO users (name, role, username, password) VALUES (?,?,?,?)",
                (s_name, "student", s_user, hash_password("1234")),
            )
            sid = scur.lastrowid
            student_ids[s_user] = sid
            conn.execute(
                "INSERT INTO class_members (student_id, class_id, year) VALUES (?,?,?)",
                (sid, s_cid, year_str),
            )

        now_ts = time.strftime("%Y-%m-%d %H:%M:%S")
        sample_entries = [
            ("student", student_ids["noam"], 3, 3, t1_id, "הגעה מוקדמת לתפילה", now_ts),
            ("student", student_ids["noam"], 5, 5, t1_id, "עזרה לחבר בכיתה", now_ts),
            ("student", student_ids["noam"], 1, 2, t1_id, "תלבושת מלאה", now_ts),
            ("student", student_ids["uri"], 4, 5, t1_id, "הצטיינות במבצע חל\"ל", now_ts),
            ("student", student_ids["itai"], 3, 3, t1_id, "הגעה בזמן", now_ts),
            ("student", student_ids["daniel"], 5, 5, t2_id, "דרך ארץ", now_ts),
            ("student", student_ids["eyal"], 4, 5, t2_id, "מבצע חל\"ל", now_ts),
            ("student", student_ids["shachar"], 5, 5, t1_id, "התנהגות למופת", now_ts),
            ("class", c1_id, 6, 5, t1_id, "כיתה נקייה ומסודרת", now_ts),
            ("class", c1_id, 8, 10, t1_id, "קישוט כיתה מצטיין", now_ts),
            ("class", c2_id, 6, 5, t2_id, "סדר וניקיון", now_ts),
            ("class", c3_id, 9, 2, t1_id, "הרמת כיסאות בסוף היום", now_ts),
        ]
        conn.executemany(
            "INSERT INTO entries (target_type, target_id, criterion_id, delta, teacher_id, note, ts) VALUES (?,?,?,?,?,?,?)",
            sample_entries,
        )
    conn.commit()
    conn.close()


# ── Auth helpers ──────────────────────────────────────────────────────────────

def hash_password(pw: str) -> str:
    return hashlib.sha256(f"{SECRET}:{pw}".encode()).hexdigest()


def make_session_token(user_id: int, role: str) -> str:
    payload = f"{user_id}:{role}:{int(time.time())}"
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{payload}:{sig}"


def verify_session_token(token: str):
    parts = token.split(":")
    if len(parts) != 4:
        return None
    uid, role, ts, sig = parts
    payload = f"{uid}:{role}:{ts}"
    expected = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected):
        return None
    # token expires after 24h
    if int(time.time()) - int(ts) > 86400:
        return None
    return {"id": int(uid), "role": role}


# ── JSON API helpers ──────────────────────────────────────────────────────────

def json_response(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", len(body))
    handler.end_headers()
    handler.wfile.write(body)


def json_error(handler, msg, status=400):
    json_response(handler, {"error": msg}, status)


def read_json(handler):
    length = int(handler.headers.get("Content-Length", 0))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    return data


def require_auth(handler):
    token = (handler.headers.get("Authorization") or "").removeprefix("Bearer ")
    if not token:
        cookie = handler.headers.get("Cookie") or ""
        for c in cookie.split(";"):
            c = c.strip()
            if c.startswith("token="):
                token = c[6:]
                break
    if not token:
        return None
    return verify_session_token(token)


def require_role(handler, *roles):
    user = require_auth(handler)
    if not user:
        json_error(handler, "נדרשת התחברות", 401)
        return None
    if user["role"] not in roles:
        json_error(handler, "אין הרשאה", 403)
        return None
    return user


# ── Routes ────────────────────────────────────────────────────────────────────

class PointServer(http.server.BaseHTTPRequestHandler):
    """Single-threaded; for production use waitress/gunicorn."""

    # Speed up the common static-file path by skipping per-request logging
    def log_message(self, fmt, *args):
        return

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization,Content-Type")
        self.end_headers()

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")

    # ── routing ───────────────────────────────────────────────────────────────

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/"):
            self._handle_api("GET", path)
        else:
            self.serve_static(path)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        self._handle_api("POST", path)

    def do_PUT(self):
        path = urllib.parse.urlparse(self.path).path
        self._handle_api("PUT", path)

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        self._handle_api("DELETE", path)

    def _handle_api(self, method, path):
        try:
            if path == "/api/login":
                return self.api_login()
            if path == "/api/logout":
                return self.api_logout()
            if path == "/api/me":
                return self.api_me()
            if path == "/api/kiosk" and method == "GET":
                return self.api_kiosk()

            user = require_auth(self)
            if not user:
                return json_error(self, "נדרשת התחברות", 401)

            # ── Admin routes ──
            if path == "/api/users" and method == "GET":
                return self.api_list_users()
            if path == "/api/users" and method == "POST":
                return self.api_create_user()
            if path.startswith("/api/users/") and method == "PUT":
                return self.api_update_user(path)
            if path.startswith("/api/users/") and method == "DELETE":
                return self.api_delete_user(path)
            if path == "/api/classes" and method == "GET":
                return self.api_list_classes()
            if path == "/api/classes" and method == "POST":
                return self.api_create_class()
            if path.startswith("/api/classes/") and method == "PUT":
                return self.api_update_class(path)
            if path.startswith("/api/classes/") and method == "DELETE":
                return self.api_delete_class(path)
            if path == "/api/criteria" and method == "GET":
                return self.api_list_criteria()
            if path == "/api/criteria" and method == "POST":
                return self.api_create_criterion()
            if path.startswith("/api/criteria/") and method == "PUT":
                return self.api_update_criterion(path)
            if path == "/api/class-members" and method == "POST":
                return self.api_add_class_member()
            if path.startswith("/api/class-members/") and method == "DELETE":
                return self.api_remove_class_member(path)

            # ── Teacher routes ──
            if path == "/api/entries" and method == "POST":
                return self.api_add_entry()
            if path.startswith("/api/entries/") and method == "DELETE":
                return self.api_cancel_entry(path)

            # ── Shared reads ──
            if path == "/api/rankings/classes":
                return self.api_class_rankings()
            if path == "/api/rankings/students":
                return self.api_student_rankings()
            if path == "/api/student-score":
                return self.api_student_score()
            if path == "/api/class-score":
                return self.api_class_score()
            if path == "/api/history":
                return self.api_history()
            if path == "/api/export":
                return self.api_export()
            if path == "/api/dashboard":
                return self.api_dashboard()

            json_error(self, "לא נמצא", 404)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return json_error(self, "בקשה לא תקינה", 400)

    # ── Static file serving ───────────────────────────────────────────────────

    def serve_static(self, path):
        rel = path.lstrip("/") or "index.html"
        allowed = rel in PUBLIC_STATIC_FILES or (
            rel.startswith("assets/") and rel.endswith(".svg") and "/" not in rel[len("assets/"):]
        )
        if not allowed:
            self.send_error(404)
            return
        file_path = (APP_DIR / rel).resolve()
        if not file_path.is_relative_to(APP_DIR.resolve()) or not file_path.is_file():
            self.send_error(404)
            return
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".webmanifest": "application/manifest+json",
        }
        ct = content_types.get(file_path.suffix, "application/octet-stream")
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_cors()
        if ct.startswith("text/html") or ct in ("text/css; charset=utf-8", "application/javascript; charset=utf-8"):
            self.send_header("Cache-Control", "public, max-age=60, stale-while-revalidate=300")
        else:
            self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    # ── Auth APIs ─────────────────────────────────────────────────────────────

    def api_login(self):
        data = read_json(self)
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        conn = get_db()
        row = conn.execute(
            "SELECT id, name, role, password, active FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if not row or row["active"] == 0:
            conn.close()
            return json_error(self, "שם משתמש או סיסמה שגויים", 401)
        if row["password"] != hash_password(password):
            conn.close()
            return json_error(self, "שם משתמש או סיסמה שגויים", 401)
        token = make_session_token(row["id"], row["role"])
        conn.close()
        json_response(self, {
            "token": token,
            "user": {"id": row["id"], "name": row["name"], "role": row["role"]},
        })

    def api_logout(self):
        json_response(self, {"ok": True})

    def api_me(self):
        user = require_auth(self)
        if not user:
            return json_error(self, "נדרשת התחברות", 401)
        conn = get_db()
        row = conn.execute("SELECT id, name, role, username, active FROM users WHERE id = ?", (user["id"],)).fetchone()
        conn.close()
        if not row:
            return json_error(self, "משתמש לא נמצא", 404)
        json_response(self, dict(row))

    # ── User management (admin only) ──────────────────────────────────────────

    def api_list_users(self):
        user = require_role(self, "admin", "teacher")
        if not user:
            return
        conn = get_db()
        rows = conn.execute("SELECT id, name, role, username, active FROM users ORDER BY name").fetchall()
        conn.close()
        json_response(self, [dict(r) for r in rows])

    def api_create_user(self):
        admin = require_role(self, "admin")
        if not admin:
            return
        data = read_json(self)
        name = (data.get("name") or "").strip()
        role = (data.get("role") or "student").strip()
        username = (data.get("username") or "").strip()
        password = data.get("password") or "123456"
        if not name or not username:
            return json_error(self, "שם ושם משתמש חובה")
        if role not in ("admin", "teacher", "student"):
            return json_error(self, "תפקיד לא חוקי")
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO users (name, role, username, password) VALUES (?,?,?,?)",
                (name, role, username, hash_password(password)),
            )
            conn.commit()
            uid = cur.lastrowid
            conn.close()
            json_response(self, {"id": uid, "name": name, "role": role, "username": username}, 201)
        except sqlite3.IntegrityError:
            conn.close()
            json_error(self, "שם משתמש כבר קיים", 409)

    def api_update_user(self, path):
        admin = require_role(self, "admin")
        if not admin:
            return
        uid = int(path.rsplit("/", 1)[-1])
        data = read_json(self)
        conn = get_db()
        # update fields
        for field in ("name", "role", "username", "active", "pin"):
            if field in data:
                conn.execute(f"UPDATE users SET {field} = ? WHERE id = ?", (data[field], uid))
        if "password" in data and data["password"]:
            conn.execute("UPDATE users SET password = ? WHERE id = ?", (hash_password(data["password"]), uid))
        if "barcode" in data:
            conn.execute("UPDATE users SET barcode = ? WHERE id = ?", (data["barcode"], uid))
        conn.commit()
        conn.close()
        json_response(self, {"ok": True})

    def api_delete_user(self, path):
        admin = require_role(self, "admin")
        if not admin:
            return
        uid = int(path.rsplit("/", 1)[-1])
        conn = get_db()
        conn.execute("UPDATE users SET active = 0 WHERE id = ?", (uid,))
        conn.commit()
        conn.close()
        json_response(self, {"ok": True})

    # ── Class management (admin) ──────────────────────────────────────────────

    def api_list_classes(self):
        user = require_auth(self)
        if not user:
            return json_error(self, "נדרשת התחברות", 401)
        conn = get_db()
        rows = conn.execute("""
            SELECT c.id, c.name, c.grade, c.teacher_id, u.name as teacher_name,
                   (SELECT COUNT(*) FROM class_members cm WHERE cm.class_id = c.id) as student_count
            FROM classes c LEFT JOIN users u ON c.teacher_id = u.id
            ORDER BY c.grade, c.name
        """).fetchall()
        conn.close()
        json_response(self, [dict(r) for r in rows])

    def api_create_class(self):
        admin = require_role(self, "admin")
        if not admin:
            return
        data = read_json(self)
        name = (data.get("name") or "").strip()
        if not name:
            return json_error(self, "שם כיתה חובה")
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO classes (name, grade, teacher_id) VALUES (?,?,?)",
                (name, data.get("grade", ""), data.get("teacher_id")),
            )
            conn.commit()
            cid = cur.lastrowid
            conn.close()
            json_response(self, {"id": cid, "name": name}, 201)
        except sqlite3.IntegrityError:
            conn.close()
            json_error(self, "כיתה כבר קיימת", 409)

    def api_update_class(self, path):
        admin = require_role(self, "admin")
        if not admin:
            return
        cid = int(path.rsplit("/", 1)[-1])
        data = read_json(self)
        conn = get_db()
        for field in ("name", "grade", "teacher_id"):
            if field in data:
                conn.execute(f"UPDATE classes SET {field} = ? WHERE id = ?", (data[field], cid))
        conn.commit()
        conn.close()
        json_response(self, {"ok": True})

    def api_delete_class(self, path):
        admin = require_role(self, "admin")
        if not admin:
            return
        cid = int(path.rsplit("/", 1)[-1])
        conn = get_db()
        conn.execute("DELETE FROM class_members WHERE class_id = ?", (cid,))
        conn.execute("DELETE FROM classes WHERE id = ?", (cid,))
        conn.commit()
        conn.close()
        json_response(self, {"ok": True})

    # ── Criteria (admin) ──────────────────────────────────────────────────────

    def api_list_criteria(self):
        user = require_auth(self)
        if not user:
            return json_error(self, "נדרשת התחברות", 401)
        conn = get_db()
        rows = conn.execute("SELECT * FROM criteria ORDER BY kind, id").fetchall()
        conn.close()
        json_response(self, [dict(r) for r in rows])

    def api_create_criterion(self):
        admin = require_role(self, "admin")
        if not admin:
            return
        data = read_json(self)
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO criteria (name,kind,add_value,sub_value,daily_limit,active) VALUES (?,?,?,?,?,?)",
            (data["name"], data["kind"], data.get("add_value", 1), data.get("sub_value", 0),
             data.get("daily_limit", 1), data.get("active", 1)),
        )
        conn.commit()
        cid = cur.lastrowid
        conn.close()
        json_response(self, {"id": cid}, 201)

    def api_update_criterion(self, path):
        admin = require_role(self, "admin")
        if not admin:
            return
        cid = int(path.rsplit("/", 1)[-1])
        data = read_json(self)
        conn = get_db()
        for field in ("name", "kind", "add_value", "sub_value", "daily_limit", "active"):
            if field in data:
                conn.execute(f"UPDATE criteria SET {field} = ? WHERE id = ?", (data[field], cid))
        conn.commit()
        conn.close()
        json_response(self, {"ok": True})

    # ── Class members (admin) ─────────────────────────────────────────────────

    def api_add_class_member(self):
        admin = require_role(self, "admin")
        if not admin:
            return
        data = read_json(self)
        conn = get_db()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO class_members (student_id, class_id, year) VALUES (?,?,?)",
                (data["student_id"], data["class_id"], data.get("year", str(time.localtime().tm_year))),
            )
            conn.commit()
            conn.close()
            json_response(self, {"ok": True}, 201)
        except sqlite3.IntegrityError:
            conn.close()
            json_error(self, "שגיאה בשיוך", 400)

    def api_remove_class_member(self, path):
        admin = require_role(self, "admin")
        if not admin:
            return
        # path: /api/class-members/<student_id>/<class_id>
        parts = path.split("/")
        sid, cid = int(parts[-2]), int(parts[-1])
        conn = get_db()
        conn.execute("DELETE FROM class_members WHERE student_id = ? AND class_id = ?", (sid, cid))
        conn.commit()
        conn.close()
        json_response(self, {"ok": True})

    # ── Point entries (teacher) ───────────────────────────────────────────────

    def api_add_entry(self):
        teacher = require_role(self, "teacher", "admin")
        if not teacher:
            return
        data = read_json(self)
        conn = get_db()
        # batch: data can have "target_ids" list for multi-student
        target_ids = data.get("target_ids") or [data.get("target_id")]
        target_type = data["target_type"]  # "student" or "class"
        crit_id = data["criterion_id"]
        crit = conn.execute("SELECT add_value, sub_value, daily_limit FROM criteria WHERE id = ? AND active = 1", (crit_id,)).fetchone()
        if not crit:
            conn.close()
            return json_error(self, "קריטריון לא נמצא")
        delta = data["delta"]  # positive = add, negative = subtract
        if delta > 0:
            delta = min(delta, crit["add_value"])
        else:
            delta = max(delta, -crit["sub_value"])

        # daily limit check (ignores cancelled=1 entries; applies to both student & class criteria)
        if crit["daily_limit"] and delta > 0 and target_type in ("student", "class"):
            today = time.strftime("%Y-%m-%d")
            start_today = f"{today} 00:00:00"
            end_today = f"{today} 23:59:59"
            for tid in target_ids:
                cnt = conn.execute(
                    "SELECT COUNT(*) FROM entries WHERE target_type=? AND target_id=? AND criterion_id=? AND delta>0 AND cancelled=0 AND ts >= ? AND ts <= ?",
                    (target_type, int(tid), crit_id, start_today, end_today),
                ).fetchone()[0]
                if cnt >= crit["daily_limit"]:
                    conn.close()
                    return json_error(self, "הגעת למגבלה היומית לקריטריון זה")

        note = data.get("note", "")
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        ids = []
        for tid in target_ids:
            cur = conn.execute(
                "INSERT INTO entries (target_type, target_id, criterion_id, delta, teacher_id, note, ts) VALUES (?,?,?,?,?,?,?)",
                (target_type, int(tid), crit_id, delta, teacher["id"], note, now),
            )
            ids.append(cur.lastrowid)
        conn.commit()
        conn.close()
        json_response(self, {"ids": ids, "delta": delta}, 201)

    def api_cancel_entry(self, path):
        teacher = require_role(self, "teacher", "admin")
        if not teacher:
            return
        eid = int(path.rsplit("/", 1)[-1])
        conn = get_db()
        entry = conn.execute("SELECT teacher_id, ts FROM entries WHERE id = ?", (eid,)).fetchone()
        if not entry:
            conn.close()
            return json_error(self, "רשומה לא נמצאה", 404)
        # 24h window for self-cancel, admin can always cancel
        if teacher["role"] != "admin":
            if entry["teacher_id"] != teacher["id"]:
                conn.close()
                return json_error(self, "ניתן לבטל רק פעולות שלך", 403)
            elapsed = time.time() - time.mktime(time.strptime(entry["ts"], "%Y-%m-%d %H:%M:%S"))
            if elapsed > 86400:
                conn.close()
                return json_error(self, "ניתן לבטל רק עד 24 שעות", 403)
        conn.execute("UPDATE entries SET cancelled = 1 WHERE id = ?", (eid,))
        conn.commit()
        conn.close()
        json_response(self, {"ok": True})

    # ── Score / rankings ──────────────────────────────────────────────────────

    def _student_score(self, sid, conn):
        personal = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN cancelled=0 THEN delta ELSE 0 END),0) FROM entries WHERE target_type='student' AND target_id=?",
            (sid,),
        ).fetchone()[0]
        return personal

    def _class_score(self, cid, conn):
        direct = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN cancelled=0 THEN delta ELSE 0 END),0) FROM entries WHERE target_type='class' AND target_id=?",
            (cid,),
        ).fetchone()[0]
        # Average personal score of class members — single aggregate query avoids N+1
        row = conn.execute("""
            SELECT COUNT(DISTINCT cm.student_id) as member_count,
                   COALESCE(SUM(CASE WHEN e.cancelled=0 THEN e.delta ELSE 0 END), 0) as personal_total
            FROM class_members cm
            LEFT JOIN entries e ON e.target_type='student' AND e.target_id=cm.student_id
            WHERE cm.class_id = ?
        """, (cid,)).fetchone()
        if row and row["member_count"]:
            avg = row["personal_total"] / row["member_count"]
            return direct + int(avg * 0.5)  # 50% weight to personal average
        return direct

    def api_student_score(self):
        user = require_auth(self)
        if not user:
            return json_error(self, "נדרשת התחברות", 401)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        sid = int(params.get("id", [user["id"]])[0])
        if user["role"] == "student" and sid != user["id"]:
            return json_error(self, "אין הרשאה לצפות בתלמיד אחר", 403)
        conn = get_db()
        score = self._student_score(sid, conn)
        # breakdown by criterion
        breakdown = conn.execute("""
            SELECT e.criterion_id, cr.name, cr.kind, SUM(CASE WHEN e.cancelled=0 THEN e.delta ELSE 0 END) as total
            FROM entries e JOIN criteria cr ON e.criterion_id = cr.id
            WHERE e.target_type='student' AND e.target_id=?
            GROUP BY e.criterion_id ORDER BY total DESC
        """, (sid,)).fetchall()
        conn.close()
        json_response(self, {"student_id": sid, "score": score, "breakdown": [dict(r) for r in breakdown]})

    def api_class_score(self):
        user = require_auth(self)
        if not user:
            return json_error(self, "נדרשת התחברות", 401)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        cid = int(params["id"][0])
        conn = get_db()
        score = self._class_score(cid, conn)
        # member list with scores
        members = conn.execute("""
            SELECT u.id, u.name, cm.class_id
            FROM class_members cm JOIN users u ON cm.student_id = u.id
            WHERE cm.class_id = ? AND u.active = 1
            ORDER BY u.name
        """, (cid,)).fetchall()
        member_data = []
        for m in members:
            s = self._student_score(m["id"], conn)
            member_data.append({"id": m["id"], "name": m["name"], "score": s})
        conn.close()
        json_response(self, {"class_id": cid, "score": score, "members": member_data})

    def _get_ranked_classes(self, conn):
        classes = conn.execute("SELECT id, name, grade FROM classes ORDER BY grade, name").fetchall()
        ranked = []
        for c in classes:
            score = self._class_score(c["id"], conn)
            ranked.append({"id": c["id"], "name": c["name"], "grade": c["grade"], "score": score})
        ranked.sort(key=lambda x: -x["score"])
        for i, r in enumerate(ranked):
            r["rank"] = i + 1
        return ranked

    def api_class_rankings(self):
        user = require_auth(self)
        if not user:
            return json_error(self, "נדרשת התחברות", 401)
        conn = get_db()
        ranked = self._get_ranked_classes(conn)
        conn.close()
        json_response(self, ranked)

    def api_kiosk(self):
        """Public read-only Hallway TV Kiosk endpoint (zero student PII)."""
        conn = get_db()
        ranked = self._get_ranked_classes(conn)
        conn.close()
        json_response(self, ranked)

    def api_student_rankings(self):
        user = require_role(self, "teacher", "admin")
        if not user:
            return
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        class_id = params.get("class_id", [None])[0]
        conn = get_db()
        if class_id:
            members = conn.execute(
                "SELECT u.id, u.name FROM class_members cm JOIN users u ON cm.student_id=u.id WHERE cm.class_id=? AND u.active=1",
                (int(class_id),),
            ).fetchall()
        else:
            members = conn.execute("SELECT id, name FROM users WHERE role='student' AND active=1").fetchall()
        ranked = []
        for m in members:
            score = self._student_score(m["id"], conn)
            ranked.append({"id": m["id"], "name": m["name"], "score": score})
        ranked.sort(key=lambda x: -x["score"])
        for i, r in enumerate(ranked):
            r["rank"] = i + 1
        conn.close()
        json_response(self, ranked)

    # ── History ───────────────────────────────────────────────────────────────

    def api_history(self):
        user = require_auth(self)
        if not user:
            return json_error(self, "נדרשת התחברות", 401)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        limit = int(params.get("limit", [50])[0])
        target_type = params.get("target_type", [None])[0]
        target_id = params.get("target_id", [None])[0]
        conn = get_db()
        query = """
            SELECT e.id, e.target_type, e.target_id, e.delta, e.note, e.ts, e.cancelled,
                   cr.name as criterion, u.name as teacher_name
            FROM entries e
            JOIN criteria cr ON e.criterion_id = cr.id
            JOIN users u ON e.teacher_id = u.id
            WHERE 1=1
        """
        args = []
        if user["role"] == "student":
            # student can see: own personal entries + class entries for their class
            query += " AND ((e.target_type='student' AND e.target_id=?) OR (e.target_type='class' AND e.target_id IN (SELECT class_id FROM class_members WHERE student_id=?)))"
            args.extend([user["id"], user["id"]])
        elif target_type and target_id:
            query += " AND e.target_type=? AND e.target_id=?"
            args.extend([target_type, int(target_id)])
        query += " ORDER BY e.ts DESC LIMIT ?"
        args.append(limit)
        rows = conn.execute(query, args).fetchall()
        conn.close()
        json_response(self, [dict(r) for r in rows])

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def api_dashboard(self):
        user = require_auth(self)
        if not user:
            return json_error(self, "נדרשת התחברות", 401)
        conn = get_db()
        result = {}
        if user["role"] == "student":
            score = self._student_score(user["id"], conn)
            # find class
            cr = conn.execute(
                "SELECT c.id, c.name FROM class_members cm JOIN classes c ON cm.class_id=c.id WHERE cm.student_id=?",
                (user["id"],),
            ).fetchone()
            if cr:
                class_score = self._class_score(cr["id"], conn)
                # rank
                all_classes = conn.execute("SELECT id FROM classes").fetchall()
                ranks = sorted([(c["id"], self._class_score(c["id"], conn)) for c in all_classes], key=lambda x: -x[1])
                rank = next(i + 1 for i, (cid, _) in enumerate(ranks) if cid == cr["id"])
                result = {"personal": score, "class_name": cr["name"], "class_score": class_score,
                          "class_rank": rank, "total_classes": len(ranks)}
            else:
                result = {"personal": score}
        elif user["role"] in ("teacher", "admin"):
            total_students = conn.execute("SELECT COUNT(*) FROM users WHERE role='student' AND active=1").fetchone()[0]
            total_classes = conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
            recent = conn.execute("""
                SELECT e.id, e.target_type, e.target_id, e.delta, cr.name as criterion, u.name as teacher_name, e.ts
                FROM entries e JOIN criteria cr ON e.criterion_id=cr.id JOIN users u ON e.teacher_id=u.id
                WHERE e.cancelled=0 ORDER BY e.ts DESC LIMIT 10
            """).fetchall()
            # get target names
            enhanced = []
            for r in recent:
                d = dict(r)
                if r["target_type"] == "student":
                    tr = conn.execute("SELECT name FROM users WHERE id=?", (r["target_id"],)).fetchone()
                    d["target_name"] = tr["name"] if tr else "?"
                else:
                    tr = conn.execute("SELECT name FROM classes WHERE id=?", (r["target_id"],)).fetchone()
                    d["target_name"] = tr["name"] if tr else "?"
                enhanced.append(d)
            result = {"total_students": total_students, "total_classes": total_classes, "recent": enhanced}
        conn.close()
        json_response(self, result)

    # ── Export ────────────────────────────────────────────────────────────────

    def api_export(self):
        user = require_role(self, "admin", "teacher")
        if not user:
            return
        conn = get_db()
        # export as CSV
        rows = conn.execute("""
            SELECT e.id, e.target_type, e.target_id,
                   CASE WHEN e.target_type='student' THEN (SELECT name FROM users WHERE id=e.target_id)
                        ELSE (SELECT name FROM classes WHERE id=e.target_id) END as target,
                   cr.name as criterion, e.delta, u.name as teacher, e.note, e.ts, e.cancelled
            FROM entries e
            JOIN criteria cr ON e.criterion_id=cr.id
            JOIN users u ON e.teacher_id=u.id
            ORDER BY e.ts DESC
        """).fetchall()
        buf = io.StringIO(newline="")
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writerow(["id", "target_type", "target_id", "target", "criterion", "delta", "teacher", "note", "ts", "cancelled"])
        for r in rows:
            sanitized = []
            for v in r:
                if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
                    sanitized.append("'" + v)
                else:
                    sanitized.append(v)
            writer.writerow(sanitized)
        body = buf.getvalue().encode("utf-8-sig")
        self.send_response(200)
        self.send_cors()
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", "attachment; filename=points_export.csv")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    global DB_DEFAULT  # noqa: PLW0603
    parser = argparse.ArgumentParser(description="SchoolMeritPoints Server")
    parser.add_argument("--port", type=int, default=8080, help="Listen port")
    parser.add_argument("--db", default=DB_DEFAULT, help="SQLite database path")
    args = parser.parse_args()
    DB_DEFAULT = args.db
    init_db()
    server = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), PointServer)
    print(f"SchoolMeritPoints running on http://0.0.0.0:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
