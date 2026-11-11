# English Placement Test — Private Quiz Website

## Features
- Shared exam code for all students.
- Student enters name and optional student number.
- Question order is randomized separately for each attempt.
- The correct-answer key is stored server-side and is never sent to the student browser.
- Students see only a submission confirmation, never their score.
- Admin-only dashboard shows student attempts, scores, and per-question responses.
- Admin can set the answer key and open/close the exam.

## Important source-file audit
The uploaded Word document contains **90 question stems**, not 90. It does not visibly mark correct answers (no bold, highlight, or answer key was found). Question IDs with fewer than four choices: 90.
The last question is incomplete in the source and needs its missing option checked before publishing. Do not launch until you have verified the question list and entered the full answer key in the Admin dashboard.

## Run locally (Windows)
1. Install Python 3.10+.
2. Extract the ZIP.
3. Open Command Prompt inside this folder.
4. Run:
   `py -m venv .venv`
   `.venv\\Scripts\\activate`
   `pip install -r requirements.txt`
5. Set secrets before running:
   `set EXAM_CODE=YourPrivateExamCode`
   `set ADMIN_PASSWORD=YourStrongAdminPassword`
   `set FLASK_SECRET_KEY=put-a-long-random-secret-here`
6. Run:
   `py app.py`
7. Open `http://127.0.0.1:5000`
8. Admin login: `http://127.0.0.1:5000/admin`

## Hosting
This ZIP is a runnable application source, not a live public website. To let students access it over the internet, deploy it to a server/hosting provider that supports Python/Flask and persistent storage. Set the three environment variables above to strong private values, use HTTPS, and keep the SQLite database on persistent storage. Do not use the sample default passwords/codes.

## Notes
- The included app is a starter implementation. Before a real exam, test student and admin flows, set the answer key, and confirm backups/hosting.
- Shared exam code controls entry, but it does not prove student identity. Collect a student name and ID if identity matters.
