# SchoolMeritPoints — GitHub Copilot Repository Instructions

## Project Overview

**SchoolMeritPoints** (`נקודות זכות`) is a zero-dependency, bilingual (Hebrew RTL / English LTR) Progressive Web App (PWA) for tracking personal student and classroom merit points in schools.

- **Dual Runtime Architecture**:
  1. **Live Server Mode ([server.py](../server.py))**: Pure Python 3.9+ standard library (`http.server.ThreadingHTTPServer`, `sqlite3` in `WAL` mode with `timeout=10.0`, `hmac`/`hashlib`, `csv`) serving allowlisted static assets and `/api/*` REST endpoints.
  2. **Serverless Web Demo Mode ([index.html](../index.html) → `localApi()`)**: Embedded `localStorage`-backed engine (`smp_demo_db_v1`) allowing the full app to run on GitHub Pages with zero backend.

## Mandatory Invariants (Never Break)

1. **Zero External Runtime Dependencies**:
   - Backend uses Python 3 standard library only (no `pip` packages, no `requirements.txt`, no `cache: 'pip'` in CI).
   - Frontend remains vanilla HTML5/CSS3/ES2022 inside [index.html](../index.html) and [spec.html](../spec.html) (no `npm`, no bundlers).
2. **Dual-Runtime Parity ([server.py](../server.py) ↔ [index.html](../index.html) ↔ [README.md](../README.md))**:
   - Every `/api/*` endpoint (including public `GET /api/kiosk`) added or modified in [server.py](../server.py) MUST have a matching handler in `localApi()` inside [index.html](../index.html) and be documented in the REST API table in [README.md](../README.md).
   - Scoring math and `daily_limit` enforcement (ignoring `cancelled=1` entries across both `student` and `class` targets) must stay identical across both runtimes:
     $$\text{ClassScore}(c) = \sum_{e \in \text{Direct}(c)} \Delta_e + \left\lfloor 0.5 \times \frac{1}{|S_c|} \sum_{s \in S_c} \text{StudentScore}(s) \right\rfloor$$
3. **Bilingual Parity (`I18N.he` ↔ `I18N.en` & `DATA_EN_MAP`)**:
   - Keep `I18N.he` and `I18N.en` key sets 100% identical in [index.html](../index.html).
   - Every `data-i18n` and `data-i18n-ph` attribute in the DOM must exist in both `I18N.he` and `I18N.en`.
   - Seeded Hebrew criteria, class names, and backend error strings must have English mappings in `DATA_EN_MAP`.
4. **Security, 3-Tier RBAC & Student Privacy**:
   - `PointServer.serve_static()` serves only `PUBLIC_STATIC_FILES` (`index.html`, `spec.html`, `manifest.webmanifest`, `icon.svg`) and `assets/*.svg` verified with `.resolve().is_relative_to(APP_DIR.resolve())`.
   - Roles: `student`, `teacher`, `admin`. Students can NEVER read another student's personal score (`403 Forbidden` on `/api/student-score?id=...` and `/api/rankings/students`) or mutate entries.
   - Teachers can undo (`DELETE /api/entries/:id`) only their own entries within 24 hours; Admins can undo any entry anytime.
   - CSV export (`/api/export`) uses `csv.writer` (RFC 4180 quote doubling) and prefixes formula-triggering characters (`=`, `+`, `-`, `@`) with `'`.
5. **Responsive & Accessible UI**:
   - Maintain layout rules across Mobile (`<768px`), Tablet (`768px–1023px`), and Desktop (`≥1024px`), Light/Dark themes (`[data-theme="dark"]`), `:focus-visible`, `prefers-reduced-motion: reduce`, `aria-live="polite"`, and valid XML `viewBox` on all SVGs.
6. **Documentation Consolidation & Quality Gate**:
   - Single-owner documentation: [README.md](../README.md) owns quick-start & API reference; [spec.md](../spec.md) owns product/criteria/schema specs; [ROADMAP.md](../ROADMAP.md) owns `SMP-xxx` sprints & `ISS-xxx` issues. Do not duplicate large tables across files.
   - Before completing any change, run `python3 -m unittest discover -s tests -v` and update [tests/](../tests/).

