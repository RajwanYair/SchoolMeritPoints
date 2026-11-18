# Security Policy

## Reporting a Vulnerability

אם מצאת פרצת אבטחה, אנא דווח ישירות לבעל המאגר במקום לפתוח Issue פומבי.

## Security Model

- סיסמאות מגובבות (SHA-256 + HMAC salt) — לא נשמרות כטקסט נקי
- JWT tokens עם תוקף 24 שעות
- RBAC: שלוש רמות הרשאה (student, teacher, admin)
- תלמידים אינם יכולים לצפות בנתוני תלמידים אחרים
- כל פעולת ניקוד מתועדת עם זהות המורה וחתימת זמן

## Production Deployment

לפריסה בסביבת ייצור:

1. הגדר משתנה סביבה `POINTS_SECRET` לערך אקראי חזק (64 תווים)
2. הרץ מאחורי reverse proxy עם HTTPS (nginx, caddy)
3. החלף את סיסמת ברירת המחדל של `admin`
4. שקול להשתמש ב-WSGI server (gunicorn, waitress) במקום `http.server`