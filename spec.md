# School Merit Points — Specification

**Version 1.0 (Draft) · November 16, 2026**

> This document describes what the system does and how it works. It's written for someone new to the project — whether you're a developer, designer, or school staff member wondering what this thing is.

---

## Table of Contents

1. [What is this?](#1-what-is-this)
2. [Who uses it?](#2-who-uses-it)
3. [How the merit system works](#3-how-the-merit-system-works)
4. [Logging in](#4-logging-in)
5. [What the screens look like](#5-what-the-screens-look-like)
6. [Visual style](#6-visual-style)
7. [How data is stored](#7-how-data-is-stored)
8. [Privacy and security](#8-privacy-and-security)
9. [Technology options](#9-technology-options)
10. [Development roadmap](#10-development-roadmap)
11. [Acceptance checklist](#11-acceptance-checklist)
12. [Open questions for the school](#12-open-questions-for-the-school)

---

## 1. What is this?

A **web app** that tracks merit points for students and classrooms. Teachers award or deduct points for behavior and classroom activities. Students see their personal score, their class score, and how their class ranks compared to others.

The core idea: positive reinforcement, quickly. A teacher should be able to give points to an entire class in under 30 seconds.

### ✅ Included in v1

- Personal points per student (earn and lose)
- Class-wide points
- Reason + timestamp recorded for every action
- Leaderboards: students within a class, and classes across the school
- Full history of who did what and when

### ❌ Not in v1 (maybe later)

- Grades, official attendance, or government system integration
- Chat / messaging between users
- Points store / redeeming points for prizes (Phase 2)
- Parent app (Phase 3)

---

## 2. Who uses it?

### Teacher

- Adds or removes points for: a single student, a group, or an entire class
- Adds a short note to any action (optional)
- Can undo their own mistake within 24 hours
- Views all classes, rankings, and history
- Scans a student QR/barcode to award a point instantly (e.g., at the gate in the morning)

### Student

- Sees their personal score, broken down by category
- Sees their class score and where it ranks among other classes
- Sees history: when, why, and how many points
- Does **not** see other students' personal scores (recommended — see §8)
- Cannot change any data

> **Recommendation:** Add a third role — **Admin** (principal or social coordinator) — who manages classes, students, teachers, point values, prints QR cards, and resets periods. Without this role, every change requires contacting the vendor.

---

## 3. How the merit system works

### Categories

The table below is a starting proposal. The admin can change values, add categories, or disable them without coding.

| Category | Type | Frequency | Add | Deduct |
|---|---|---|---|---|
| School uniform | Personal | Daily | +2 | −1 |
| Tzitzit | Personal | Daily | +2 | −1 |
| Punctuality | Personal | Daily | +3 | −2 |
| Special assignment | Personal | Per campaign | +5 | — |
| Respectful conduct | Personal | As needed | +5 | −3 |
| Classroom tidiness | Class | Daily | +5 | −3 |
| Clean walls | Class | Weekly | +3 | −3 |
| Decorated classroom | Class | Monthly | +10 | — |
| Chairs up at end of day | Class | Daily | +2 | −2 |
| Class duty roster | Class | Daily | +3 | −2 |
| Organized cubbies | Class | Weekly | +3 | −2 |

### How scores are calculated

- **Personal score** = sum of all points earned minus points lost
- **Class score** = direct class points + **average** of personal scores of students in that class (average, not sum — so bigger classes don't get an unfair advantage)
- Daily categories can be limited to once per student per day
- Scores run in **periods** (monthly, semester, yearly). At period start, the leaderboard resets but history is preserved
- Scores never drop below zero (configurable)

---

## 4. Logging in

**Flow:** Welcome screen → Choose Teacher/Student → Username+password *or* Scan QR code → Dashboard

### Password login

- Username = student ID number or a name set by admin
- Initial password issued by admin; must be changed on first login
- "Remember me" option on personal devices
- Temporary lockout after 5 wrong attempts
- Password reset handled by admin (students may not have email)

### QR code login

- Every student and teacher has a personal printed QR card
- The code contains a random ID — no name, no ID number
- Lost cards are revoked with one click; new ones printed instantly
- Teachers: QR code + 4-digit PIN (because teachers have write access)
- The same card also lets teachers scan a student to award a point quickly

---

## 5. What the screens look like

> Visual mockups with CSS styling are in **`spec.html`** (the Hebrew visual reference). Here's a text summary:

### Welcome / Login
- Gold star logo at top
- Student / Teacher tab toggle
- Username + password fields
- "Login" button + "Scan QR code" alternative
- "Forgot password? Ask your homeroom teacher" link

### Student dashboard
- Greeting: "Hello, [Name] · [Class]"
- Large card: monthly score with progress bar
- Mini cards: class score, class ranking position
- Recent activity feed with date, teacher, and ± amount
- Bottom tabs: Home · My Class · Rankings · History

### Teacher — Awarding points
- Class dropdown picker
- Personal / Class tab
- Category selector (chip buttons)
- Student list with checkboxes showing current score
- "Select all" shortcut
- Green Add / Red Deduct action buttons
- Bottom tabs: Award · Scan · Rankings · History

### Desktop — Class rankings
- Top nav: Class Rankings · Students · Settings
- Leaderboard table: rank, class name, bar, score
- Side panel: live activity feed

---

## 6. Visual style

### Principles

- Full Hebrew, right-to-left on every screen
- Large buttons: designed for one-handed phone use in a hallway
- Green = add, Red = deduct (always)
- Big prominent score numbers; details below
- Brief star animation when a student earns points
- Light + dark mode
- Accessibility: Israeli Standard 5568 (Level AA)

### Proposed colors

| Role | Color |
|---|---|
| School identity (frame, buttons, headings) | Blue |
| Points and stars | Gold |
| Adding points | Green |
| Deducting points | Red |

If the school has official branding, it replaces the blue. Suggested fonts: **Secular One** (headings), **Assistant** (body) — both free and support Hebrew.

---

## 7. How data is stored

| Table | Key fields | Notes |
|---|---|---|
| **Users** | ID, name, role, username, hashed password, QR code, active | No national ID needed |
| **Classes** | ID, name (e.g. "6-2"), grade, homeroom teacher | |
| **Enrollment** | Student, class, school year | Year transitions don't lose history |
| **Categories** | Name, type (personal/class), add value, deduct value, daily limit, active | Admin-editable |
| **Point actions** | ID, target, category, change (±), teacher, timestamp, note, cancelled | Never deleted; only flagged as cancelled |
| **Periods** | Name, start date, end date | For monthly/yearly leaderboards |

> Scores are always recalculated from the action log — never stored as a single number. This means every point is traceable and mistakes can be undone cleanly.

---

## 8. Privacy and security

- Users are minors. The system stores only: name, class, score. No ID numbers, addresses, phones, or photos.
- Vendor must comply with Israeli privacy law and Ministry of Education data guidelines. The school should verify with their legal advisor.
- Parents should be notified about the system and what data is collected.
- Students see only their own score + their class score. Public personal rankings are **disabled by default** — the school decides.
- HTTPS, hashed passwords, daily automated backups, servers in Europe/Israel.
- Every point change is logged with teacher name and timestamp.
- Data belongs to the school. Full Excel export available anytime.

---

## 9. Technology options

| Option | What it is | Pros | Cons |
|---|---|---|---|
| **PWA** ⭐ Recommended | A website installable on the home screen | One codebase, no app stores, instant updates, camera access | Slightly less "app-like" than native |
| **Native app** | Separate Android + iPhone + admin site | Smooth UX, notifications | More expensive, two codebases, app store approval |
| **No-code** | Glide / AppSheet / similar | Fast pilot | Limited design & Hebrew, platform lock-in, per-user fees |

Always ask the vendor: monthly hosting cost, annual maintenance, who owns the code and data.

---

## 10. Development roadmap

### Phase 1 — MVP (6–8 weeks)
- Welcome + login (password & QR)
- Student dashboard + Teacher dashboard
- Award/deduct personal & class points
- Class rankings + history
- Manage classes, students, categories
- Excel import for students
- Print QR cards

### Phase 2 — Extensions (after 1-month pilot)
- Points store / redeem for prizes
- Hallway TV live rankings display
- Auto-generated excellence certificates
- Reports for homeroom teachers and principal

### Phase 3 — Parents (as needed)
- Parent view-only login
- Weekly automated parent updates
- Student notifications

---

## 11. Acceptance checklist

1. Teacher awards a point to 30 students in under 30 seconds.
2. QR scan logs in a student within 3 seconds.
3. Point change appears on student screen within 1 minute, no manual refresh.
4. Works on Android, iPhone, and desktop (Chrome, Safari, Edge).
5. Full Hebrew RTL UI, no clipped or reversed text.
6. Student cannot see another student's personal score or change data.
7. Admin adds a class/student/category without vendor help.
8. Full Excel export.
9. Teacher + admin guide and 1-hour staff training.
10. 3 months bug-fix warranty after go-live.

---

## 12. Open questions for the school

- How many students, classes, and teachers? (affects hosting cost)
- Do all students have phones, or is a school viewing station needed?
- Should students see in-class personal rankings, or just their own score?
- Can points be deducted for every category, or only some?
- Monthly, semester, or yearly period? What's the prize?
- Who will be the system admin at the school?
- Can teachers award points to any student, or only their own classes?
- What exactly is a "special assignment" and how is it tracked?

---

*Draft specification. Values, timelines, and mockups are a starting point for vendor discussions and are not binding.*