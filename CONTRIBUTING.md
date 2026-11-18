# Contributing to SchoolMeritPoints

תודה על הרצון לתרום! הנה הנחיות ברורות לתרומה נקייה.

## How to Contribute / איך לתרום

1. **Fork** the repository / **Fork** את המאגר.
2. Create a descriptive branch: / צור ענף עם שם תיאורי:
   ```bash
   git checkout -b feature/my-feature
   ```
3. Make your changes / בצע את השינויים שלך.
4. Run the automated test suite and make sure all **23 tests** pass:
   הרץ את חבילת הבדיקות האוטומטית וודא שכל **23 הבדיקות** עוברות:
   ```bash
   python3 -m unittest discover -s tests -v
   ```
   *(Recommended: enable the pre-commit hook / מומלץ להפעיל את ה-hook: `git config core.hooksPath .githooks`)*
5. Verify it works by running `python3 server.py` and testing in a browser.
   וודא שהקוד עובד — הרץ `python3 server.py` ובדוק בדפדפן.
6. **Commit** with a clear message in English or Hebrew / עם תיאור ברור באנגלית או בעברית.
7. **Push** to your fork / **Push** ל-fork שלך.
8. Open a **Pull Request** / פתח **Pull Request**.

## Code Style / סגנון קוד

- **Python**: follow PEP 8.
- **HTML / CSS / JS**: keep your changes consistent with the existing code.
- **Comments**: Hebrew comments are welcome / הערות בעברית יתקבלו בברכה.

## Reporting Bugs / דיווח על באגים

Open an Issue with:
- Problem description / תיאור הבעיה
- Steps to reproduce / צעדים לשחזור
- Python version / גרסת Python
- Screenshot if relevant / צילום מסך אם רלוונטי

## Feature Ideas / רעיונות לשיפורים

Feel free to open an Issue with an idea for discussion before starting work.
מוזמן לפתוח Issue עם רעיון — נדון בו לפני שמתחילים לעבוד.