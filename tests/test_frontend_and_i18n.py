#!/usr/intel/bin/python3
"""Tests for frontend HTML/CSS/JS, Bilingual (EN/HE) i18n parity, Dark/Light mode, and PC/Tablet/Mobile responsiveness."""

from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT_DIR = Path(__file__).resolve().parent.parent


class _DOMInspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.i18n_keys = set()
        self.i18n_ph_keys = set()
        self.dirs = {}

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if "id" in attr_dict:
            self.ids.add(attr_dict["id"])
            if "dir" in attr_dict:
                self.dirs[attr_dict["id"]] = attr_dict["dir"]
        if "data-i18n" in attr_dict:
            self.i18n_keys.add(attr_dict["data-i18n"])
        if "data-i18n-ph" in attr_dict:
            self.i18n_ph_keys.add(attr_dict["data-i18n-ph"])


class TestFrontendAndI18n(unittest.TestCase):
    """Validate index.html and spec.html methods, i18n dictionaries, themes, and responsive rules."""

    @classmethod
    def setUpClass(cls):
        cls.index_html = (ROOT_DIR / "index.html").read_text(encoding="utf-8")
        cls.spec_html = (ROOT_DIR / "spec.html").read_text(encoding="utf-8")

    def test_01_index_html_dom_and_views(self):
        """Verify index.html parses cleanly and contains all required role apps, views, and controls."""
        inspector = _DOMInspector()
        inspector.feed(self.index_html)

        required_ids = {
            "splash",
            "loginPage",
            "segStudent",
            "segTeacher",
            "loginUser",
            "loginPass",
            "loginBtn",
            "loginErr",
            "modeBadge",
            "resetDemoBtn",
            "appStudent",
            "viewStudentHome",
            "viewStudentClass",
            "viewStudentRank",
            "viewStudentHist",
            "appTeacher",
            "viewTeacherScore",
            "viewTeacherRank",
            "viewTeacherHist",
            "appAdmin",
            "viewAdminUsers",
            "viewAdminClasses",
            "viewAdminCriteria",
            "viewAdminScore",
            "viewAdminRank",
            "viewAdminExport",
            "classPicker",
            "genericModal",
            "toast",
        }
        for rid in required_ids:
            self.assertIn(rid, inspector.ids, f"Missing required DOM id #{rid} in index.html")

    def test_02_all_frontend_js_functions_defined(self):
        """Verify every JavaScript function in index.html is defined."""
        expected_functions = [
            "createInitialDemoDb",
            "getDemoDb",
            "saveDemoDb",
            "resetDemoStore",
            "setModeUI",
            "calcStudentScore",
            "calcClassScore",
            "localApi",
            "api",
            "quickDemoLogin",
            "t",
            "trData",
            "applyI18n",
            "toggleLang",
            "showSplash",
            "hideSplash",
            "showLogin",
            "showApp",
            "toast",
            "toggleTheme",
            "setLoginRole",
            "doLogin",
            "doLogout",
            "setupUser",
            "loadApp",
            "fmtDate",
            "loadStudent",
            "renderStudentRecent",
            "loadStudentClassView",
            "loadStudentRankView",
            "loadStudentHistView",
            "switchStudentView",
            "loadTeacher",
            "loadAdmin",
            "loadClasses",
            "loadStudentsForClass",
            "toggleStudent",
            "toggleAllStudents",
            "loadCriteria",
            "renderChips",
            "selectCriterion",
            "setEntryKind",
            "pickClass",
            "selectClass",
            "closeClassPicker",
            "doQuick",
            "doAddPoints",
            "doSubPoints",
            "doPoints",
            "setRankView",
            "loadRankings",
            "switchTeacherView",
            "loadHistory",
            "cancelEntry",
            "switchAdminView",
            "loadAdminUsers",
            "showUserModal",
            "closeModal",
            "doCreateUser",
            "deleteUser",
            "loadAdminClasses",
            "showClassModal",
            "doCreateClass",
            "deleteClass",
            "loadAdminCriteria",
            "showCriterionModal",
            "doCreateCriterion",
            "toggleCriterion",
            "doExport",
            "boot",
        ]
        for fn in expected_functions:
            pattern = rf"\bfunction\s+{re.escape(fn)}\s*\("
            self.assertRegex(self.index_html, pattern, f"Missing JS function {fn}() in index.html")

    def test_03_bilingual_i18n_dictionary_parity_and_dom_coverage(self):
        """Ensure I18N.he and I18N.en have identical keys and cover every data-i18n attribute in index.html."""
        he_match = re.search(r"he:\s*\{(.*?)\n\s*\},\s*\n\s*en:\s*\{(.*?)\n\s*\}", self.index_html, re.S)
        self.assertIsNotNone(he_match, "Could not locate I18N.he and I18N.en blocks in index.html")
        he_block, en_block = he_match.group(1), he_match.group(2)

        he_keys = set(re.findall(r"^\s*([a-zA-Z0-9_]+)\s*:", he_block, re.M))
        en_keys = set(re.findall(r"^\s*([a-zA-Z0-9_]+)\s*:", en_block, re.M))

        self.assertEqual(
            he_keys,
            en_keys,
            f"I18N key mismatch between he and en: he-en={he_keys - en_keys}, en-he={en_keys - he_keys}",
        )
        self.assertGreaterEqual(len(he_keys), 70)

        inspector = _DOMInspector()
        inspector.feed(self.index_html)
        for k in inspector.i18n_keys | inspector.i18n_ph_keys:
            self.assertIn(k, he_keys, f"DOM data-i18n key '{k}' missing from I18N.he")
            self.assertIn(k, en_keys, f"DOM data-i18n key '{k}' missing from I18N.en")

        # Verify DATA_EN_MAP translates all 11 built-in criteria and 3 default classes
        for item in (
            "תלבושת",
            "ציצית",
            "הגעה בזמן",
            'מבצע חל"ל',
            "התנהגות בדרך ארץ",
            "סדר וניקיון הכיתה",
            "קירות נקיים",
            "כיתה מקושטת",
            "הרמת כיסאות בסוף היום",
            "תורנים כיתתיים",
            "כוורות מסודרות",
            "ו'1",
            "ו'2",
            "ז'1",
        ):
            self.assertIn(item, self.index_html, f"Missing translation entry for '{item}' in DATA_EN_MAP")

    def test_04_responsive_pc_tablet_mobile_and_dark_light_modes(self):
        """Verify responsive media queries (Tablet 768px, PC 1024px) and Dark/Light mode rules exist."""
        self.assertIn("@media (min-width: 768px)", self.index_html)
        self.assertIn("@media (min-width: 1024px)", self.index_html)
        self.assertIn('[data-theme="dark"]', self.index_html)
        self.assertIn("prefers-color-scheme: dark", self.index_html)

    def test_05_spec_html_bilingual_and_theme_support(self):
        """Verify spec.html has bilingual Hebrew (RTL) & English (LTR) containers and theme/lang functions."""
        inspector = _DOMInspector()
        inspector.feed(self.spec_html)
        self.assertIn("wrapHe", inspector.ids)
        self.assertIn("wrapEn", inspector.ids)
        self.assertEqual(inspector.dirs.get("wrapHe"), "rtl")
        self.assertEqual(inspector.dirs.get("wrapEn"), "ltr")

        for fn in ("applySpecLang", "toggleSpecLang", "toggleSpecTheme"):
            self.assertRegex(self.spec_html, rf"\bfunction\s+{fn}\s*\(")


if __name__ == "__main__":
    unittest.main()
