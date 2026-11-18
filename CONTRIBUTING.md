# Contributing to SchoolMeritPoints

תודה על הרצון לתרום! הנה כמה הנחיות פשוטות.

## איך לתרום

1. **Fork** את המאגר
2. צור branch עם שם תיאורי: `git checkout -b feature/my-feature`
3. בצע את השינויים שלך
4. הרץ את חבילת הבדיקות האוטומטית וודא שכל 16 הבדיקות עוברות:
   ```bash
   python3 -m unittest discover -s tests -v
   ```
   *(מומלץ להפעיל גם את ה-pre-commit hook: `git config core.hooksPath .githooks`)*
5. וודא שהקוד עובד — הרץ `python3 server.py` ובדוק בדפדפן
6. **Commit** עם תיאור ברור בעברית או באנגלית
6. **Push** ל-fork שלך
7. פתח **Pull Request**

## סגנון קוד

- Python: עקוב אחר PEP 8
- HTML/CSS/JS: שמור על עקביות עם הקוד הקיים
- הערות בעברית יתקבלו בברכה

## דיווח על באגים

פתח Issue עם:
- תיאור הבעיה
- צעדים לשחזור
- גרסת Python
- צילום מסך (אם רלוונטי)

## רעיונות לשיפורים

מוזמן לפתוח Issue עם רעיון — נדון בו לפני שמתחילים לעבוד.