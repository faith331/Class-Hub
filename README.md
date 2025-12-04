
# ClassHub — Homepage + Auth (Fixed)

- New homepage with a top lineup (tabs), search bar, and chips — inspired by your screenshot.
- **Register / Login** (email + password + role) restored.
- Teacher and Student dashboards + features preserved: Announcements, Assignments (with grading), Discussions, Quizzes (auto-score).

## Run (Windows/macOS/Linux)
```bash
cd ClassHub_HomepageAuth_Fixed
python -m venv venv
venv\Scripts\activate     # on Windows
# source venv/bin/activate   # on macOS/Linux
pip install flask
python app.py
```
Open: http://127.0.0.1:5000

Demo users seeded:
- Teacher: teacher@classhub.local / password123
- Student: student@classhub.local / password123
