---
mode: agent
description: "Run the full SchoolMeritPoints quality gate: Python syntax, HTML/SVG/Manifest validation, i18n parity, and unittest suite."
---

# Audit Parity & Run Full Quality Gate

1. Run the full test suite and asset validators:
   - `python3 -m py_compile server.py`
   - `python3 -m unittest discover -s tests -v`
2. Check parity across:
   - [server.py](../../server.py) `/api/*` routes vs `localApi()` in [index.html](../../index.html) vs the API table in [README.md](../../README.md).
   - `I18N.he` vs `I18N.en` keys and `data-i18n` / `data-i18n-ph` attributes in [index.html](../../index.html).
   - Sprint and issue statuses in [ROADMAP.md](../../ROADMAP.md).
3. Report any discrepancies and fix them with test coverage.
