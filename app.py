import os
import re
import logging
from flask import Flask, jsonify, request, render_template
from db import init_db, get_db
import subprocess
from datetime import datetime

PORT = int(os.environ.get('PORT', 5001))
DEBUG = os.environ.get('DEBUG', '').lower() in ('1', 'true', 'yes')
API_TOKEN = os.environ.get('API_TOKEN', '')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'minimax-m2.7:cloud')

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
init_db()

MODULES = ["applications", "interviews", "tasks", "projects", "meetings", "contacts"]

# --- Auth ---

@app.before_request
def check_auth():
    if not API_TOKEN or not request.path.startswith('/api/'):
        return
    auth = request.headers.get('Authorization', '')
    if auth != f'Bearer {API_TOKEN}':
        return jsonify({"error": "Unauthorized"}), 401

# --- Global error handler ---

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error("Unhandled error: %s", e, exc_info=True)
    return jsonify({"error": "Internal server error"}), 500

# --- Validation helpers ---

_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

def _require(data, *fields):
    missing = [f for f in fields if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    return None

def _check_date(value, field='date'):
    if value is not None and not _DATE_RE.match(str(value)):
        return jsonify({"error": f"'{field}' must be YYYY-MM-DD"}), 400
    return None

def _check_enum(value, valid_set, field):
    if value is not None and value not in valid_set:
        return jsonify({"error": f"'{field}' must be one of: {', '.join(sorted(valid_set))}"}), 400
    return None

# --- Global search ---

@app.route('/api/search')
def global_search():
    q = request.args.get('q', '').strip().lower()
    if not q:
        return jsonify({"applications": [], "tasks": [], "projects": [], "meetings": [], "contacts": []})
    db = get_db()
    try:
        results = {}
        results['applications'] = [dict(r) for r in db.execute(
            "SELECT * FROM applications WHERE LOWER(company) LIKE ? OR LOWER(role) LIKE ? OR LOWER(notes) LIKE ? LIMIT 5",
            (f'%{q}%', f'%{q}%', f'%{q}%')
        ).fetchall()]
        results['tasks'] = [dict(r) for r in db.execute(
            "SELECT * FROM tasks WHERE LOWER(title) LIKE ? OR LOWER(notes) LIKE ? LIMIT 5",
            (f'%{q}%', f'%{q}%')
        ).fetchall()]
        results['projects'] = [dict(r) for r in db.execute(
            "SELECT * FROM projects WHERE LOWER(name) LIKE ? OR LOWER(description) LIKE ? LIMIT 5",
            (f'%{q}%', f'%{q}%')
        ).fetchall()]
        results['meetings'] = [dict(r) for r in db.execute(
            "SELECT * FROM meetings WHERE LOWER(person_name) LIKE ? OR LOWER(topics) LIKE ? OR LOWER(outcome) LIKE ? LIMIT 5",
            (f'%{q}%', f'%{q}%', f'%{q}%')
        ).fetchall()]
        results['contacts'] = [dict(r) for r in db.execute(
            "SELECT * FROM contacts WHERE LOWER(name) LIKE ? OR LOWER(company) LIKE ? OR LOWER(notes) LIKE ? LIMIT 5",
            (f'%{q}%', f'%{q}%', f'%{q}%')
        ).fetchall()]
        return jsonify(results)
    except Exception as e:
        logger.error("global_search error: %s", e)
        return jsonify({"error": "Search failed"}), 500

# --- Interviews API ---

_INTERVIEW_COLS = ('date', 'type', 'notes', 'outcome')
_INTERVIEW_TYPES = frozenset({'phone', 'video', 'onsite'})

@app.route('/api/interviews', methods=['GET'])
def list_interviews():
    db = get_db()
    try:
        app_id = request.args.get('application_id')
        if app_id:
            rows = db.execute(
                "SELECT i.*, a.company, a.role FROM interviews i "
                "JOIN applications a ON i.application_id = a.id "
                "WHERE i.application_id = ? ORDER BY i.date DESC", (app_id,)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT i.*, a.company, a.role FROM interviews i "
                "JOIN applications a ON i.application_id = a.id ORDER BY i.date DESC"
            ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        logger.error("list_interviews error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/interviews', methods=['POST'])
def create_interview():
    data = request.get_json() or {}
    err = _require(data, 'application_id', 'date', 'type')
    if err: return err
    err = _check_date(data['date'])
    if err: return err
    err = _check_enum(data['type'], _INTERVIEW_TYPES, 'type')
    if err: return err
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO interviews (application_id, date, type, notes, outcome) VALUES (?, ?, ?, ?, ?)",
            (data['application_id'], data['date'], data['type'], data.get('notes', ''), data.get('outcome', 'pending'))
        )
        db.commit()
        return jsonify({"id": cursor.lastrowid}), 201
    except Exception as e:
        logger.error("create_interview error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/interviews/<int:interview_id>', methods=['PUT'])
def update_interview(interview_id):
    data = request.get_json() or {}
    err = _check_date(data.get('date'))
    if err: return err
    err = _check_enum(data.get('type'), _INTERVIEW_TYPES, 'type')
    if err: return err
    sets, vals = [], []
    for k in _INTERVIEW_COLS:
        if k in data:
            sets.append(f"{k} = ?")
            vals.append(data[k])
    if not sets:
        return jsonify({"error": "No fields to update"}), 400
    vals.append(interview_id)
    db = get_db()
    try:
        db.execute(f"UPDATE interviews SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("update_interview error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/interviews/<int:interview_id>', methods=['DELETE'])
def delete_interview(interview_id):
    db = get_db()
    try:
        db.execute("DELETE FROM interviews WHERE id = ?", (interview_id,))
        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("delete_interview error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def status():
    return jsonify({"status": "ok", "modules": MODULES})

# --- Applications API ---

_APP_COLS = ('status', 'notes', 'company', 'role', 'date_applied')
_APP_STATUSES = frozenset({'applied', 'interview', 'rejected', 'offer'})

@app.route('/api/applications', methods=['GET'])
def list_applications():
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM applications ORDER BY date_applied DESC").fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        logger.error("list_applications error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/applications', methods=['POST'])
def create_application():
    data = request.get_json() or {}
    err = _require(data, 'company', 'role', 'date_applied')
    if err: return err
    err = _check_date(data['date_applied'], 'date_applied')
    if err: return err
    err = _check_enum(data.get('status'), _APP_STATUSES, 'status')
    if err: return err
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO applications (company, role, date_applied, status, notes) VALUES (?, ?, ?, ?, ?)",
            (data['company'], data['role'], data['date_applied'], data.get('status', 'applied'), data.get('notes', ''))
        )
        db.commit()
        return jsonify({"id": cursor.lastrowid}), 201
    except Exception as e:
        logger.error("create_application error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/applications/<int:app_id>', methods=['PUT'])
def update_application(app_id):
    data = request.get_json() or {}
    err = _check_date(data.get('date_applied'), 'date_applied')
    if err: return err
    err = _check_enum(data.get('status'), _APP_STATUSES, 'status')
    if err: return err
    sets, vals = [], []
    for k in _APP_COLS:
        if k in data:
            sets.append(f"{k} = ?")
            vals.append(data[k])
    if not sets:
        return jsonify({"error": "No fields to update"}), 400
    vals.append(app_id)
    db = get_db()
    try:
        db.execute(f"UPDATE applications SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("update_application error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/applications/<int:app_id>', methods=['DELETE'])
def delete_application(app_id):
    db = get_db()
    try:
        db.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("delete_application error: %s", e)
        return jsonify({"error": "Database error"}), 500

# --- Tasks API ---

_TASK_COLS = ('title', 'status', 'priority', 'due_date', 'notes')
_TASK_STATUSES = frozenset({'todo', 'started', 'done'})
_TASK_PRIORITIES = frozenset({'low', 'medium', 'high'})

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    db = get_db()
    try:
        status = request.args.get('status')
        if status:
            rows = db.execute("SELECT * FROM tasks WHERE status=? ORDER BY priority DESC, due_date ASC", (status,)).fetchall()
        else:
            rows = db.execute("SELECT * FROM tasks ORDER BY status, priority DESC, due_date ASC").fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        logger.error("list_tasks error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/tasks', methods=['POST'])
def create_task():
    data = request.get_json() or {}
    err = _require(data, 'title')
    if err: return err
    err = _check_enum(data.get('status'), _TASK_STATUSES, 'status')
    if err: return err
    err = _check_enum(data.get('priority'), _TASK_PRIORITIES, 'priority')
    if err: return err
    err = _check_date(data.get('due_date'), 'due_date')
    if err: return err
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO tasks (title, status, priority, due_date, notes) VALUES (?, ?, ?, ?, ?)",
            (data['title'], data.get('status', 'todo'), data.get('priority', 'medium'), data.get('due_date'), data.get('notes', ''))
        )
        db.commit()
        return jsonify({"id": cursor.lastrowid}), 201
    except Exception as e:
        logger.error("create_task error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.get_json() or {}
    err = _check_enum(data.get('status'), _TASK_STATUSES, 'status')
    if err: return err
    err = _check_enum(data.get('priority'), _TASK_PRIORITIES, 'priority')
    if err: return err
    err = _check_date(data.get('due_date'), 'due_date')
    if err: return err
    sets, vals = [], []
    for k in _TASK_COLS:
        if k in data:
            sets.append(f"{k} = ?")
            vals.append(data[k])
    if not sets:
        return jsonify({"error": "No fields to update"}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(task_id)
    db = get_db()
    try:
        db.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("update_task error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    db = get_db()
    try:
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("delete_task error: %s", e)
        return jsonify({"error": "Database error"}), 500

# --- Projects API ---

_PROJ_COLS = ('name', 'type', 'status', 'description', 'repo_url')
_PROJ_TYPES = frozenset({'coding', 'idea', 'open'})
_PROJ_STATUSES = frozenset({'active', 'paused', 'done'})

@app.route('/api/projects', methods=['GET'])
def list_projects():
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM projects ORDER BY status, last_updated DESC").fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        logger.error("list_projects error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/projects', methods=['POST'])
def create_project():
    data = request.get_json() or {}
    err = _require(data, 'name')
    if err: return err
    err = _check_enum(data.get('type'), _PROJ_TYPES, 'type')
    if err: return err
    err = _check_enum(data.get('status'), _PROJ_STATUSES, 'status')
    if err: return err
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO projects (name, type, status, description, repo_url) VALUES (?, ?, ?, ?, ?)",
            (data['name'], data.get('type', 'open'), data.get('status', 'active'), data.get('description', ''), data.get('repo_url', ''))
        )
        db.commit()
        return jsonify({"id": cursor.lastrowid}), 201
    except Exception as e:
        logger.error("create_project error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/projects/<int:proj_id>', methods=['PUT'])
def update_project(proj_id):
    data = request.get_json() or {}
    err = _check_enum(data.get('type'), _PROJ_TYPES, 'type')
    if err: return err
    err = _check_enum(data.get('status'), _PROJ_STATUSES, 'status')
    if err: return err
    sets, vals = [], []
    for k in _PROJ_COLS:
        if k in data:
            sets.append(f"{k} = ?")
            vals.append(data[k])
    if not sets:
        return jsonify({"error": "No fields to update"}), 400
    sets.append("last_updated = CURRENT_TIMESTAMP")
    vals.append(proj_id)
    db = get_db()
    try:
        db.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("update_project error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/projects/<int:proj_id>', methods=['DELETE'])
def delete_project(proj_id):
    db = get_db()
    try:
        db.execute("DELETE FROM projects WHERE id = ?", (proj_id,))
        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("delete_project error: %s", e)
        return jsonify({"error": "Database error"}), 500

# --- Meetings API ---

_MEETING_COLS = ('person_name', 'date', 'topics', 'outcome', 'next_steps')

@app.route('/api/meetings', methods=['GET'])
def list_meetings():
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM meetings ORDER BY date DESC").fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        logger.error("list_meetings error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/meetings', methods=['POST'])
def create_meeting():
    data = request.get_json() or {}
    err = _require(data, 'person_name', 'date')
    if err: return err
    err = _check_date(data['date'])
    if err: return err
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO meetings (person_name, date, topics, outcome, next_steps) VALUES (?, ?, ?, ?, ?)",
            (data['person_name'], data['date'], data.get('topics', ''), data.get('outcome', ''), data.get('next_steps', ''))
        )
        db.execute("UPDATE contacts SET last_contact_date = ? WHERE name = ?", (data['date'], data['person_name']))
        db.commit()
        return jsonify({"id": cursor.lastrowid}), 201
    except Exception as e:
        logger.error("create_meeting error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/meetings/<int:meet_id>', methods=['PUT'])
def update_meeting(meet_id):
    data = request.get_json() or {}
    err = _check_date(data.get('date'))
    if err: return err
    sets, vals = [], []
    for k in _MEETING_COLS:
        if k in data:
            sets.append(f"{k} = ?")
            vals.append(data[k])
    if not sets:
        return jsonify({"error": "No fields to update"}), 400
    vals.append(meet_id)
    db = get_db()
    try:
        db.execute(f"UPDATE meetings SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("update_meeting error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/meetings/<int:meet_id>', methods=['DELETE'])
def delete_meeting(meet_id):
    db = get_db()
    try:
        db.execute("DELETE FROM meetings WHERE id = ?", (meet_id,))
        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("delete_meeting error: %s", e)
        return jsonify({"error": "Database error"}), 500

# --- Contacts API ---

_CONTACT_COLS = ('name', 'relationship', 'company', 'last_contact_date', 'notes')
_RELATIONSHIPS = frozenset({'colleague', 'friend', 'recruiter', 'other'})

@app.route('/api/contacts', methods=['GET'])
def list_contacts():
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM contacts ORDER BY name").fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        logger.error("list_contacts error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/contacts', methods=['POST'])
def create_contact():
    data = request.get_json() or {}
    err = _require(data, 'name')
    if err: return err
    err = _check_enum(data.get('relationship'), _RELATIONSHIPS, 'relationship')
    if err: return err
    err = _check_date(data.get('last_contact_date'), 'last_contact_date')
    if err: return err
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO contacts (name, relationship, company, last_contact_date, notes) VALUES (?, ?, ?, ?, ?)",
            (data['name'], data.get('relationship', 'other'), data.get('company', ''), data.get('last_contact_date'), data.get('notes', ''))
        )
        db.commit()
        return jsonify({"id": cursor.lastrowid}), 201
    except Exception as e:
        logger.error("create_contact error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/contacts/<int:contact_id>', methods=['PUT'])
def update_contact(contact_id):
    data = request.get_json() or {}
    err = _check_enum(data.get('relationship'), _RELATIONSHIPS, 'relationship')
    if err: return err
    err = _check_date(data.get('last_contact_date'), 'last_contact_date')
    if err: return err
    sets, vals = [], []
    for k in _CONTACT_COLS:
        if k in data:
            sets.append(f"{k} = ?")
            vals.append(data[k])
    if not sets:
        return jsonify({"error": "No fields to update"}), 400
    vals.append(contact_id)
    db = get_db()
    try:
        db.execute(f"UPDATE contacts SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("update_contact error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    db = get_db()
    try:
        db.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("delete_contact error: %s", e)
        return jsonify({"error": "Database error"}), 500

# --- Daily Log API ---

@app.route('/api/daily-log', methods=['GET'])
def list_daily_logs():
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM daily_log ORDER BY date DESC").fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        logger.error("list_daily_logs error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/daily-log/<date>', methods=['GET'])
def get_daily_log(date):
    err = _check_date(date)
    if err: return err
    db = get_db()
    try:
        row = db.execute("SELECT * FROM daily_log WHERE date = ?", (date,)).fetchone()
        if not row:
            return jsonify({"date": date, "notes": ""})
        return jsonify(dict(row))
    except Exception as e:
        logger.error("get_daily_log error: %s", e)
        return jsonify({"error": "Database error"}), 500

@app.route('/api/daily-log', methods=['POST'])
def upsert_daily_log():
    data = request.get_json() or {}
    err = _require(data, 'date')
    if err: return err
    err = _check_date(data['date'])
    if err: return err
    db = get_db()
    try:
        db.execute(
            "INSERT INTO daily_log (date, notes) VALUES (?, ?) ON CONFLICT(date) DO UPDATE SET notes = ?",
            (data['date'], data.get('notes', ''), data.get('notes', ''))
        )
        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error("upsert_daily_log error: %s", e)
        return jsonify({"error": "Database error"}), 500

# --- Heatmap API ---

@app.route('/api/heatmap')
def heatmap():
    year = request.args.get('year', str(datetime.now().year))
    if not re.match(r'^\d{4}$', year):
        return jsonify({"error": "Invalid year"}), 400
    db = get_db()
    try:
        counts = {}
        for r in db.execute("SELECT date_applied, COUNT(*) as c FROM applications WHERE strftime('%Y', date_applied)=? GROUP BY date_applied", (year,)).fetchall():
            counts[r['date_applied']] = counts.get(r['date_applied'], 0) + r['c']
        for r in db.execute("SELECT date, COUNT(*) as c FROM interviews WHERE strftime('%Y', date)=? GROUP BY date", (year,)).fetchall():
            counts[r['date']] = counts.get(r['date'], 0) + r['c']
        for r in db.execute("SELECT date(updated_at) as d, COUNT(*) as c FROM tasks WHERE status='done' AND strftime('%Y', updated_at)=? GROUP BY d", (year,)).fetchall():
            counts[r['d']] = counts.get(r['d'], 0) + r['c']
        for r in db.execute("SELECT date, COUNT(*) as c FROM meetings WHERE strftime('%Y', date)=? GROUP BY date", (year,)).fetchall():
            counts[r['date']] = counts.get(r['date'], 0) + r['c']
        for r in db.execute("SELECT date(last_updated) as d, COUNT(*) as c FROM projects WHERE strftime('%Y', last_updated)=? GROUP BY d", (year,)).fetchall():
            counts[r['d']] = counts.get(r['d'], 0) + r['c']
        return jsonify({k: v for k, v in counts.items() if k})
    except Exception as e:
        logger.error("heatmap error: %s", e)
        return jsonify({"error": "Database error"}), 500

# --- Report API ---

@app.route('/api/report', methods=['POST'])
def generate_report():
    data = request.get_json() or {}
    err = _require(data, 'start_date', 'end_date')
    if err: return err
    err = _check_date(data['start_date'], 'start_date')
    if err: return err
    err = _check_date(data['end_date'], 'end_date')
    if err: return err
    start, end = data['start_date'], data['end_date']
    modules = data.get('modules', ['applications', 'tasks', 'meetings', 'projects'])
    db = get_db()
    try:
        stats = {}
        if 'applications' in modules:
            stats['applications_sent'] = db.execute(
                "SELECT COUNT(*) as c FROM applications WHERE date_applied BETWEEN ? AND ?", (start, end)
            ).fetchone()['c']
        if 'applications' in modules or 'interviews' in modules:
            stats['interviews'] = db.execute(
                "SELECT COUNT(*) as c FROM interviews WHERE date BETWEEN ? AND ?", (start, end)
            ).fetchone()['c']
        if 'tasks' in modules:
            stats['tasks_completed'] = db.execute(
                "SELECT COUNT(*) as c FROM tasks WHERE status='done' AND date(updated_at) BETWEEN ? AND ?", (start, end)
            ).fetchone()['c']
            stats['tasks_total'] = db.execute("SELECT COUNT(*) as c FROM tasks").fetchone()['c']
        if 'meetings' in modules:
            stats['meetings'] = db.execute(
                "SELECT COUNT(*) as c FROM meetings WHERE date BETWEEN ? AND ?", (start, end)
            ).fetchone()['c']
        if 'projects' in modules:
            stats['active_projects'] = db.execute(
                "SELECT COUNT(*) as c FROM projects WHERE status='active'"
            ).fetchone()['c']
    except Exception as e:
        logger.error("generate_report DB error: %s", e)
        return jsonify({"error": "Database error"}), 500

    summary = ""
    try:
        prompt = (
            f"You are a personal productivity assistant. Summarize this activity data in 3-4 sentences, "
            f"highlighting wins and patterns.\n\nPeriod: {start} to {end}\n"
            f"Applications sent: {stats.get('applications_sent', 0)}\n"
            f"Interviews: {stats.get('interviews', 0)}\n"
            f"Tasks completed: {stats.get('tasks_completed', 0)} / {stats.get('tasks_total', 0)}\n"
            f"Meetings: {stats.get('meetings', 0)}\n"
            f"Active projects: {stats.get('active_projects', 0)}\n\nKeep it concise and motivating."
        )
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt, capture_output=True, text=True, timeout=60
        )
        summary = result.stdout.strip()
    except Exception:
        summary = f"Report for {start} to {end}: " + ", ".join(f"{k}: {v}" for k, v in stats.items()) + "."
    return jsonify({"summary": summary, "stats": stats, "generated_at": datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(port=PORT, debug=DEBUG)
