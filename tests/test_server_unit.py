#!/usr/intel/bin/python3
"""Unit tests for all standalone functions, database helpers, auth tokens, and score formulas in server.py."""

import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import server  # noqa: E402


class TestServerUnit(unittest.TestCase):
    """Test every helper function and internal score method in server.py."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._orig_db = server.DB_DEFAULT
        server.DB_DEFAULT = self._tmp.name
        server.init_db()

    def tearDown(self):
        server.DB_DEFAULT = self._orig_db
        for suffix in ("", "-wal", "-shm"):
            p = self._tmp.name + suffix
            if os.path.exists(p):
                os.unlink(p)

    def test_get_db_pragmas_and_row_factory(self):
        """get_db() returns a connection with sqlite3.Row, foreign_keys=ON, and WAL mode."""
        conn = server.get_db()
        try:
            self.assertIs(conn.row_factory, sqlite3.Row)
            fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            self.assertEqual(fk, 1)
            jm = conn.execute("PRAGMA journal_mode").fetchone()[0].lower()
            self.assertIn(jm, ("wal", "memory"))
        finally:
            conn.close()

    def test_init_db_tables_indexes_and_idempotency(self):
        """init_db() creates all 6 tables, 3 indexes, seeds default records, and is idempotent."""
        # Call init_db() a second time to verify idempotency
        server.init_db()
        conn = server.get_db()
        try:
            tables = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            for expected in ("users", "classes", "class_members", "criteria", "entries", "periods"):
                self.assertIn(expected, tables)

            indexes = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                ).fetchall()
            }
            for idx in ("idx_entries_target", "idx_entries_ts", "idx_users_role"):
                self.assertIn(idx, indexes)

            # Default admin, 2 teachers, 10 students = 13 users
            users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            self.assertEqual(users_count, 13)

            # 11 default criteria (5 personal, 6 class)
            crit_count = conn.execute("SELECT COUNT(*) FROM criteria").fetchone()[0]
            self.assertEqual(crit_count, 11)
            personal_count = conn.execute(
                "SELECT COUNT(*) FROM criteria WHERE kind='personal'"
            ).fetchone()[0]
            class_count = conn.execute(
                "SELECT COUNT(*) FROM criteria WHERE kind='class'"
            ).fetchone()[0]
            self.assertEqual(personal_count, 5)
            self.assertEqual(class_count, 6)

            # 3 demo classes
            classes_count = conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
            self.assertEqual(classes_count, 3)
        finally:
            conn.close()

    def test_hash_password_determinism_and_salting(self):
        """hash_password() produces a 64-char hex SHA-256 digest salted with SECRET."""
        h1 = server.hash_password("secret123")
        h2 = server.hash_password("secret123")
        h3 = server.hash_password("different")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertEqual(len(h1), 64)
        self.assertNotIn("secret123", h1)

    def test_make_and_verify_session_token_valid_and_invalid(self):
        """make_session_token() and verify_session_token() validate HMAC and expiration."""
        tok = server.make_session_token(42, "teacher")
        parsed = server.verify_session_token(tok)
        self.assertEqual(parsed, {"id": 42, "role": "teacher"})

        # Malformed token
        self.assertIsNone(server.verify_session_token("invalid"))
        self.assertIsNone(server.verify_session_token("a:b:c"))

        # Tampered role or signature
        parts = tok.split(":")
        tampered_role = f"{parts[0]}:admin:{parts[2]}:{parts[3]}"
        self.assertIsNone(server.verify_session_token(tampered_role))
        tampered_sig = f"{parts[0]}:{parts[1]}:{parts[2]}:0000000000000000"
        self.assertIsNone(server.verify_session_token(tampered_sig))

        # Expired token (> 86400 seconds old)
        old_ts = int(time.time()) - 90000
        payload = f"42:teacher:{old_ts}"
        sig = server.hmac.new(
            server.SECRET.encode(), payload.encode(), server.hashlib.sha256
        ).hexdigest()[:16]
        expired_tok = f"{payload}:{sig}"
        self.assertIsNone(server.verify_session_token(expired_tok))

    def test_student_and_class_score_calculations(self):
        """_student_score() and _class_score() compute exact totals and exclude cancelled entries."""
        dummy_handler = object.__new__(server.PointServer)
        conn = server.get_db()
        try:
            noam = conn.execute("SELECT id FROM users WHERE username='noam'").fetchone()
            self.assertIsNotNone(noam)
            s_score = dummy_handler._student_score(noam["id"], conn)
            # Initial seeded entries for Noam: +3 +5 +2 = 10
            self.assertEqual(s_score, 10)

            # Class 1 (ו'1): direct = +5 +10 = 15; 4 students (10, 5, 3, 0 -> avg = 4.5); 15 + int(4.5 * 0.5) = 17
            c1 = conn.execute("SELECT id FROM classes WHERE name=\"ו'1\"").fetchone()
            c_score = dummy_handler._class_score(c1["id"], conn)
            self.assertEqual(c_score, 17)

            # Empty class score should be 0
            cur = conn.execute("INSERT INTO classes (name, grade) VALUES ('ח1', 'ח')")
            empty_cid = cur.lastrowid
            self.assertEqual(dummy_handler._class_score(empty_cid, conn), 0)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
