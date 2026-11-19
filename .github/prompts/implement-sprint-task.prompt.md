---
mode: agent
description: "Implement a planned sprint task (SMP-xxx) or resolve a tracked issue (ISS-xxx) end-to-end with tests and docs."
---

# Implement Sprint Task or Issue (`SMP-xxx` / `ISS-xxx`)

Follow this workflow to implement the requested task or issue in **SchoolMeritPoints**:

1. **Read Context**:
   - Inspect the target `SMP-xxx` or `ISS-xxx` entry in [ROADMAP.md](../../ROADMAP.md) and relevant sections of [spec.md](../../spec.md).
2. **Implement Backend & Frontend Parity**:
   - Update [server.py](../../server.py) for SQLite/HTTP server mode.
   - Update `localApi()` and UI views in [index.html](../../index.html) for Serverless Web Demo mode.
   - Add any new UI strings to both `I18N.he` and `I18N.en` (and `DATA_EN_MAP` if needed).
3. **Add Automated Tests**:
   - Add unit tests in [tests/test_server_unit.py](../../tests/test_server_unit.py), HTTP API tests in [tests/test_api_endpoints.py](../../tests/test_api_endpoints.py), and DOM/JS/i18n checks in [tests/test_frontend_and_i18n.py](../../tests/test_frontend_and_i18n.py).
4. **Update Documentation & Roadmap**:
   - Update [README.md](../../README.md) if new endpoints or user-facing features were added.
   - Mark the `SMP-xxx` / `ISS-xxx` item status in [ROADMAP.md](../../ROADMAP.md).
5. **Run Quality Gate**:
   - Execute `python3 -m unittest discover -s tests -v` and ensure 100% pass rate.
