#!/usr/intel/bin/python3
"""Integration tests for all 19 REST API endpoints, RBAC permissions, static serving, and CORS in server.py."""

import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import server  # noqa: E402


class TestApiEndpoints(unittest.TestCase):
    """End-to-end HTTP test suite covering every route and method in PointServer."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls._tmp.close()
        cls._orig_db = server.DB_DEFAULT
        server.DB_DEFAULT = cls._tmp.name
        server.init_db()

        cls.httpd = server.http.server.HTTPServer(("127.0.0.1", 0), server.PointServer)
        cls.port = cls.httpd.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        server.DB_DEFAULT = cls._orig_db
        for suffix in ("", "-wal", "-shm"):
            p = cls._tmp.name + suffix
            if os.path.exists(p):
                os.unlink(p)

    def request(self, method: str, path: str, body=None, token: str | None = None, headers: dict | None = None):
        hdrs = {"Content-Type": "application/json"}
        if token:
            hdrs["Authorization"] = f"Bearer {token}"
        if headers:
            hdrs.update(headers)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                ct = resp.headers.get("Content-Type", "")
                if "application/json" in ct:
                    return resp.status, json.loads(raw.decode("utf-8")), resp.headers
                return resp.status, raw.decode("utf-8-sig"), resp.headers
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except Exception:
                parsed = raw.decode("utf-8", "replace")
            return e.code, parsed, e.headers

    def login_as(self, username: str, password: str) -> str:
        status, data, _ = self.request("POST", "/api/login", {"username": username, "password": password})
        self.assertEqual(status, 200, f"Login failed for {username}: {data}")
        return data["token"]

    def test_01_static_files_and_cors_options(self):
        """Test static file serving (/, /index.html, /spec.html, /manifest.webmanifest, /icon.svg, 404) and OPTIONS CORS."""
        status, _, hdrs = self.request("OPTIONS", "/api/login")
        self.assertEqual(status, 200)
        self.assertEqual(hdrs.get("Access-Control-Allow-Origin"), "*")

        for path in ("/", "/index.html", "/spec.html", "/manifest.webmanifest", "/icon.svg", "/assets/hero-banner.svg"):
            status, body, _ = self.request("GET", path)
            self.assertEqual(status, 200, f"Static GET {path} failed")
            self.assertTrue(len(str(body)) > 50)

        status, _, _ = self.request("GET", "/nonexistent-file.xyz")
        self.assertEqual(status, 404)

    def test_02_auth_login_logout_me_and_cookie_fallback(self):
        """Test /api/login, /api/logout, /api/me with Bearer token, Cookie header, and invalid credentials."""
        # Invalid credentials
        status, data, _ = self.request("POST", "/api/login", {"username": "admin", "password": "wrong"})
        self.assertEqual(status, 401)
        self.assertIn("error", data)

        status, _, _ = self.request("POST", "/api/login", {"username": "no_such_user", "password": "123"})
        self.assertEqual(status, 401)

        # Unauthenticated /api/me
        status, _, _ = self.request("GET", "/api/me")
        self.assertEqual(status, 401)

        # Valid login + Bearer /api/me
        admin_tok = self.login_as("admin", "admin123")
        status, me, _ = self.request("GET", "/api/me", token=admin_tok)
        self.assertEqual(status, 200)
        self.assertEqual(me["username"], "admin")
        self.assertEqual(me["role"], "admin")

        # Cookie auth fallback
        status, me_cookie, _ = self.request("GET", "/api/me", headers={"Cookie": f"token={admin_tok}"})
        self.assertEqual(status, 200)
        self.assertEqual(me_cookie["id"], me["id"])

        # Logout
        status, out, _ = self.request("POST", "/api/logout")
        self.assertEqual(status, 200)
        self.assertTrue(out["ok"])

    def test_03_user_crud_and_rbac(self):
        """Test GET/POST/PUT/DELETE /api/users and RBAC enforcement."""
        admin_tok = self.login_as("admin", "admin123")
        teacher_tok = self.login_as("david", "teacher123")
        student_tok = self.login_as("noam", "1234")

        # Student cannot list or create users
        status, _, _ = self.request("GET", "/api/users", token=student_tok)
        self.assertEqual(status, 403)
        status, _, _ = self.request("POST", "/api/users", {"name": "X", "username": "x"}, token=teacher_tok)
        self.assertEqual(status, 403)

        # Teacher can list users
        status, users, _ = self.request("GET", "/api/users", token=teacher_tok)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(users), 13)

        # Admin validation checks on create_user
        status, _, _ = self.request("POST", "/api/users", {"name": "", "username": ""}, token=admin_tok)
        self.assertEqual(status, 400)
        status, _, _ = self.request(
            "POST", "/api/users", {"name": "BadRole", "username": "badrole", "role": "superuser"}, token=admin_tok
        )
        self.assertEqual(status, 400)

        # Admin creates a new student
        status, created, _ = self.request(
            "POST",
            "/api/users",
            {"name": "Test Student", "username": "test_stu", "role": "student", "password": "pw1"},
            token=admin_tok,
        )
        self.assertEqual(status, 201)
        uid = created["id"]

        # Duplicate username returns 409
        status, _, _ = self.request(
            "POST",
            "/api/users",
            {"name": "Dup", "username": "test_stu", "role": "student"},
            token=admin_tok,
        )
        self.assertEqual(status, 409)

        # Admin updates user password, pin, and barcode
        status, upd, _ = self.request(
            "PUT",
            f"/api/users/{uid}",
            {"name": "Updated Student", "password": "pw2", "pin": "9999", "barcode": "BC-001"},
            token=admin_tok,
        )
        self.assertEqual(status, 200)
        self.assertTrue(upd["ok"])

        # Updated password works
        self.login_as("test_stu", "pw2")

        # Admin soft-deletes (deactivates) user
        status, _, _ = self.request("DELETE", f"/api/users/{uid}", token=admin_tok)
        self.assertEqual(status, 200)

        # Deactivated user can no longer log in
        status, _, _ = self.request("POST", "/api/login", {"username": "test_stu", "password": "pw2"})
        self.assertEqual(status, 401)

    def test_04_classes_and_class_members_crud(self):
        """Test /api/classes and /api/class-members CRUD and RBAC."""
        admin_tok = self.login_as("admin", "admin123")
        student_tok = self.login_as("noam", "1234")

        # Student can list classes but cannot create
        status, classes, _ = self.request("GET", "/api/classes", token=student_tok)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(classes), 3)

        status, _, _ = self.request("POST", "/api/classes", {"name": "ח'1"}, token=student_tok)
        self.assertEqual(status, 403)

        # Admin validation & creation
        status, _, _ = self.request("POST", "/api/classes", {"name": ""}, token=admin_tok)
        self.assertEqual(status, 400)

        status, new_cl, _ = self.request("POST", "/api/classes", {"name": "ח'2", "grade": "ח"}, token=admin_tok)
        self.assertEqual(status, 201)
        cid = new_cl["id"]

        # Duplicate class name -> 409
        status, _, _ = self.request("POST", "/api/classes", {"name": "ח'2", "grade": "ח"}, token=admin_tok)
        self.assertEqual(status, 409)

        # Update class
        status, _, _ = self.request("PUT", f"/api/classes/{cid}", {"grade": "ח-מצוינות"}, token=admin_tok)
        self.assertEqual(status, 200)

        # Enroll and remove class member
        status, _, _ = self.request(
            "POST", "/api/class-members", {"student_id": 4, "class_id": cid, "year": "2026"}, token=admin_tok
        )
        self.assertEqual(status, 201)

        status, _, _ = self.request("DELETE", f"/api/class-members/4/{cid}", token=admin_tok)
        self.assertEqual(status, 200)

        # Delete class
        status, _, _ = self.request("DELETE", f"/api/classes/{cid}", token=admin_tok)
        self.assertEqual(status, 200)

    def test_05_criteria_crud(self):
        """Test GET/POST/PUT /api/criteria."""
        admin_tok = self.login_as("admin", "admin123")
        student_tok = self.login_as("noam", "1234")

        status, criteria, _ = self.request("GET", "/api/criteria", token=student_tok)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(criteria), 11)

        status, _, _ = self.request("POST", "/api/criteria", {"name": "X", "kind": "personal"}, token=student_tok)
        self.assertEqual(status, 403)

        status, cr, _ = self.request(
            "POST",
            "/api/criteria",
            {"name": "התנדבות קהילתית", "kind": "personal", "add_value": 4, "sub_value": 1, "daily_limit": 2},
            token=admin_tok,
        )
        self.assertEqual(status, 201)
        cr_id = cr["id"]

        status, _, _ = self.request("PUT", f"/api/criteria/{cr_id}", {"active": 0, "add_value": 6}, token=admin_tok)
        self.assertEqual(status, 200)

    def test_06_entries_daily_limit_clamping_and_undo_rules(self):
        """Test POST /api/entries (clamping, daily limit, batch) and DELETE /api/entries/:id (24h & teacher ownership)."""
        admin_tok = self.login_as("admin", "admin123")
        david_tok = self.login_as("david", "teacher123")
        moshe_tok = self.login_as("moshe", "teacher123")
        student_tok = self.login_as("noam", "1234")

        # Student cannot add entries
        status, _, _ = self.request(
            "POST", "/api/entries", {"target_type": "student", "target_ids": [4], "criterion_id": 5, "delta": 5}, token=student_tok
        )
        self.assertEqual(status, 403)

        # Criterion 5 (התנהגות בדרך ארץ): add_value=5, sub_value=3, daily_limit=0 (unlimited)
        # Delta +99 should be clamped to +5
        status, entry_res, _ = self.request(
            "POST",
            "/api/entries",
            {"target_type": "student", "target_ids": [5, 6], "criterion_id": 5, "delta": 99, "note": "Batch test"},
            token=david_tok,
        )
        self.assertEqual(status, 201)
        self.assertEqual(entry_res["delta"], 5)
        self.assertEqual(len(entry_res["ids"]), 2)
        eid = entry_res["ids"][0]

        # Criterion 2 (ציצית): daily_limit=1. First award for student 7 succeeds, second on same day fails with 400
        status, _, _ = self.request(
            "POST",
            "/api/entries",
            {"target_type": "student", "target_ids": [7], "criterion_id": 2, "delta": 2},
            token=david_tok,
        )
        self.assertEqual(status, 201)
        status, limit_err, _ = self.request(
            "POST",
            "/api/entries",
            {"target_type": "student", "target_ids": [7], "criterion_id": 2, "delta": 2},
            token=david_tok,
        )
        self.assertEqual(status, 400)
        self.assertIn("error", limit_err)

        # Another teacher (moshe) cannot cancel david's entry
        status, _, _ = self.request("DELETE", f"/api/entries/{eid}", token=moshe_tok)
        self.assertEqual(status, 403)

        # David can cancel his own entry within 24h
        status, _, _ = self.request("DELETE", f"/api/entries/{eid}", token=david_tok)
        self.assertEqual(status, 200)

        # Admin can cancel any entry anytime
        status, _, _ = self.request("DELETE", f"/api/entries/{entry_res['ids'][1]}", token=admin_tok)
        self.assertEqual(status, 200)

        # Missing entry -> 404
        status, _, _ = self.request("DELETE", "/api/entries/999999", token=admin_tok)
        self.assertEqual(status, 404)

    def test_07_rankings_scores_dashboard_history_and_export(self):
        """Test rankings, student-score privacy, class-score, dashboard, history, CSV export, and 404 route."""
        admin_tok = self.login_as("admin", "admin123")
        david_tok = self.login_as("david", "teacher123")
        noam_tok = self.login_as("noam", "1234")  # user id 4

        # Class rankings
        status, c_ranks, _ = self.request("GET", "/api/rankings/classes", token=noam_tok)
        self.assertEqual(status, 200)
        self.assertEqual(c_ranks[0]["rank"], 1)

        # Student rankings: blocked for students (403), allowed for teachers
        status, _, _ = self.request("GET", "/api/rankings/students", token=noam_tok)
        self.assertEqual(status, 403)
        status, s_ranks, _ = self.request("GET", "/api/rankings/students?class_id=1", token=david_tok)
        self.assertEqual(status, 200)
        self.assertTrue(all("score" in r and "rank" in r for r in s_ranks))

        # Student score: Noam can see own score, blocked from seeing student #5
        status, own_score, _ = self.request("GET", "/api/student-score?id=4", token=noam_tok)
        self.assertEqual(status, 200)
        self.assertEqual(own_score["student_id"], 4)
        status, _, _ = self.request("GET", "/api/student-score?id=5", token=noam_tok)
        self.assertEqual(status, 403)

        # Class score
        status, cl_score, _ = self.request("GET", "/api/class-score?id=1", token=noam_tok)
        self.assertEqual(status, 200)
        self.assertEqual(cl_score["class_id"], 1)
        self.assertTrue(len(cl_score["members"]) >= 4)

        # Dashboard (student vs teacher)
        status, s_dash, _ = self.request("GET", "/api/dashboard", token=noam_tok)
        self.assertEqual(status, 200)
        self.assertIn("personal", s_dash)
        self.assertIn("class_rank", s_dash)

        status, t_dash, _ = self.request("GET", "/api/dashboard", token=david_tok)
        self.assertEqual(status, 200)
        self.assertIn("total_students", t_dash)
        self.assertIn("recent", t_dash)

        # History privacy filter for student
        status, s_hist, _ = self.request("GET", "/api/history?limit=50", token=noam_tok)
        self.assertEqual(status, 200)
        for h in s_hist:
            if h["target_type"] == "student":
                self.assertEqual(h["target_id"], 4)

        # CSV export: blocked for student (403), allowed for teacher/admin
        status, _, _ = self.request("GET", "/api/export", token=noam_tok)
        self.assertEqual(status, 403)

        status, csv_text, hdrs = self.request("GET", "/api/export", token=admin_tok)
        self.assertEqual(status, 200)
        self.assertIn("text/csv", hdrs.get("Content-Type", ""))
        self.assertTrue(csv_text.startswith("id,target_type,target_id,target,criterion,delta,teacher,note,ts,cancelled"))

        # Unknown API route -> 404
        status, _, _ = self.request("GET", "/api/does-not-exist", token=admin_tok)
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
