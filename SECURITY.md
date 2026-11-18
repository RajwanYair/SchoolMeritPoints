# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it directly to the repository owner instead of opening a public Issue.

אם מצאת פרצת אבטחה, אנא דווח ישירות לבעל המאגר במקום לפתוח Issue פומבי.

## Security Model

- Passwords are hashed with a salted SHA-256 HMAC, never stored in plain text.
- Sessions are signed 24-hour HMAC tokens (not JWT).
- RBAC enforces three roles: `student`, `teacher`, and `admin`.
- Students can never view another student's personal score or history.
- Every scoring action is logged with the acting teacher's identity and a timestamp.

## Production Deployment Checklist

Before deploying to production:

1. Set a strong, random `POINTS_SECRET` environment variable (at least 64 characters).
2. Run behind an HTTPS reverse proxy such as nginx or Caddy.
3. Change the default `admin` password immediately after first login.
4. Replace the built-in `http.server` with a production WSGI server such as gunicorn or waitress.