from flask import Flask, jsonify, request, render_template
from db import init_db, get_db
import subprocess
import json as _json
from datetime import datetime

app = Flask(__name__)
init_db()

MODULES = ["applications", "interviews", "tasks", "projects", "meetings", "contacts"]

@app.route('/api/search')
def global_search():
    q = request.args.get('q', '').strip().lower()
    if not q:
        return jsonify({"applications": [], "tasks": [], "projects": [], "meetings": [], "contacts": []})
    db = get_db()
    results = {}
    # Applications: company, role, notes
    rows = db.execute(
        "SELECT * FROM applications WHERE LOWER(company) LIKE ? OR LOWER(role) LIKE ? OR LOWER(notes) LIKE ? LIMIT 5",
        (f'%{q}%', f'%{q}%', f'%{q}%')
    ).fetchall()
    results['applications'] = [dict(r) for r in rows]
    # Tasks: title, notes
    rows = db.execute(
        "SELECT * FROM tasks WHERE LOWER(title) LIKE ? OR LOWER(notes) LIKE ? LIMIT 5",
        (f'%{q}%', f'%{q}%')
    ).fetchall()
    results['tasks'] = [dict(r) for r in rows]
    # Projects: name, description
    rows = db.execute(
        "SELECT * FROM projects WHERE LOWER(name) LIKE ? OR LOWER(description) LIKE ? LIMIT 5",
        (f'%{q}%', f'%{q}%')
    ).fetchall()
    results['projects'] = [dict(r) for r in rows]
    # Meetings: person_name, topics, outcome
    rows = db.execute(
        "SELECT * FROM meetings WHERE LOWER(person_name) LIKE ? OR LOWER(topics) LIKE ? OR LOWER(outcome) LIKE ? LIMIT 5",
        (f'%{q}%', f'%{q}%', f'%{q}%')
    ).fetchall()
    results['meetings'] = [dict(r) for r in rows]
    # Contacts: name, company, notes
    rows = db.execute(
        "SELECT * FROM contacts WHERE LOWER(name) LIKE ? OR LOWER(company) LIKE ? OR LOWER(notes) LIKE ? LIMIT 5",
        (f'%{q}%', f'%{q}%', f'%{q}%')
    ).fetchall()
    results['contacts'] = [dict(r) for r in rows]
    return jsonify(results)

# --- Interviews API ---

@app.route('/api/interviews', methods=['GET'])
def list_interviews():
    db = get_db()
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

@app.route('/api/interviews', methods=['POST'])
def create_interview():
    data = request.get_json()
    db = get_db()
    cursor = db.execute(
        "INSERT INTO interviews (application_id, date, type, notes, outcome) VALUES (?, ?, ?, ?, ?)",
        (data['application_id'], data['date'], data['type'], data.get('notes', ''), data.get('outcome', 'pending'))
    )
    db.commit()
    return jsonify({"id": cursor.lastrowid}), 201

@app.route('/api/interviews/<int:interview_id>', methods=['PUT'])
def update_interview(interview_id):
    data = request.get_json()
    db = get_db()
    sets, vals = [], []
    for k in ('date', 'type', 'notes', 'outcome'):
        if k in data:
            sets.append(f"{k} = ?")
            vals.append(data[k])
    if not sets:
        return jsonify({"error": "No fields to update"}), 400
    vals.append(interview_id)
    db.execute(f"UPDATE interviews SET {', '.join(sets)} WHERE id = ?", vals)
    db.commit()
    return jsonify({"ok": True})

@app.route('/api/interviews/<int:interview_id>', methods=['DELETE'])
def delete_interview(interview_id):
    db = get_db()
    db.execute("DELETE FROM interviews WHERE id = ?", (interview_id,))
    db.commit()
    return jsonify({"ok": True})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def status():
    return jsonify({"status": "ok", "modules": MODULES})

# --- Applications API ---

@app.route('/api/applications', methods=['GET'])
def list_applications():
    db = get_db()
    rows = db.execute("SELECT * FROM applications ORDER BY date_applied DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/applications', methods=['POST'])
def create_application():
    data = request.get_json()
    db = get_db()
    cursor = db.execute(
        "INSERT INTO applications (company, role, date_applied, status, notes) VALUES (?, ?, ?, ?, ?)",
        (data['company'], data['role'], data['date_applied'], data.get('status', 'applied'), data.get('notes', ''))
    )
    db.commit()
    return jsonify({"id": cursor.lastrowid}), 201

@app.route('/api/applications/<int:app_id>', methods=['PUT'])
def update_application(app_id):
    data = request.get_json()
    db = get_db()
    sets, vals = [], []
    for k in ('status', 'notes', 'company', 'role', 'date_applied'):
        if k in data:
            sets.append(f"{k} = ?")
            vals.append(data[k])
    if not sets:
        return jsonify({"error": "No fields to update"}), 400
    vals.append(app_id)
    db.execute(f"UPDATE applications SET {', '.join(sets)} WHERE id = ?", vals)
    db.commit()
    return jsonify({"ok": True})

@app.route('/api/applications/<int:app_id>', methods=['DELETE'])
def delete_application(app_id):
    db = get_db()
    db.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    db.commit()
    return jsonify({"ok": True})

# --- Tasks API ---

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    db = get_db()
    status = request.args.get('status')
    if status:
        rows = db.execute("SELECT * FROM tasks WHERE status=? ORDER BY priority DESC, due_date ASC", (status,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM tasks ORDER BY status, priority DESC, due_date ASC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/tasks', methods=['POST'])
def create_task():
    data = request.get_json()
    db = get_db()
    cursor = db.execute(
        "INSERT INTO tasks (title, status, priority, due_date, notes) VALUES (?, ?, ?, ?, ?)",
        (data['title'], data.get('status', 'todo'), data.get('priority', 'medium'), data.get('due_date'), data.get('notes', ''))
    )
    db.commit()
    return jsonify({"id": cursor.lastrowid}), 201

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.get_json()
    db = get_db()
    sets, vals = [], []
    for k in ('title', 'status', 'priority', 'due_date', 'notes'):
        if k in data:
            sets.append(f"{k} = ?")
            vals.append(data[k])
    if not sets:
        return jsonify({"error": "No fields to update"}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(task_id)
    db.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", vals)
    db.commit()
    return jsonify({"ok": True})

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return jsonify({"ok": True})

# --- Projects API ---

@app.route('/api/projects', methods=['GET'])
def list_projects():
    db = get_db()
    rows = db.execute("SELECT * FROM projects ORDER BY status, last_updated DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/projects', methods=['POST'])
def create_project():
    data = request.get_json()
    db = get_db()
    cursor = db.execute(
        "INSERT INTO projects (name, type, status, description, repo_url) VALUES (?, ?, ?, ?, ?)",
        (data['name'], data.get('type', 'open'), data.get('status', 'active'), data.get('description', ''), data.get('repo_url', ''))
    )
    db.commit()
    return jsonify({"id": cursor.lastrowid}), 201

@app.route('/api/projects/<int:proj_id>', methods=['PUT'])
def update_project(proj_id):
    data = request.get_json()
    db = get_db()
    sets, vals = [], []
    for k in ('name', 'type', 'status', 'description', 'repo_url'):
        if k in data:
            sets.append(f"{k} = ?")
            vals.append(data[k])
    if not sets:
        return jsonify({"error": "No fields to update"}), 400
    sets.append("last_updated = CURRENT_TIMESTAMP")
    vals.append(proj_id)
    db.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id = ?", vals)
    db.commit()
    return jsonify({"ok": True})

@app.route('/api/projects/<int:proj_id>', methods=['DELETE'])
def delete_project(proj_id):
    db = get_db()
    db.execute("DELETE FROM projects WHERE id = ?", (proj_id,))
    db.commit()
    return jsonify({"ok": True})

# --- Meetings API ---

@app.route('/api/meetings', methods=['GET'])
def list_meetings():
    db = get_db()
    rows = db.execute("SELECT * FROM meetings ORDER BY date DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/meetings', methods=['POST'])
def create_meeting():
    data = request.get_json()
    db = get_db()
    cursor = db.execute(
        "INSERT INTO meetings (person_name, date, topics, outcome, next_steps) VALUES (?, ?, ?, ?, ?)",
        (data['person_name'], data['date'], data.get('topics', ''), data.get('outcome', ''), data.get('next_steps', ''))
    )
    # Auto-update contact's last_contact_date if name matches
    db.execute("UPDATE contacts SET last_contact_date = ? WHERE name = ?", (data['date'], data['person_name']))
    db.commit()
    return jsonify({"id": cursor.lastrowid}), 201

@app.route('/api/meetings/<int:meet_id>', methods=['PUT'])
def update_meeting(meet_id):
    data = request.get_json()
    db = get_db()
    sets, vals = [], []
    for k in ('person_name', 'date', 'topics', 'outcome', 'next_steps'):
        if k in data:
            sets.append(f"{k} = ?")
            vals.append(data[k])
    if not sets:
        return jsonify({"error": "No fields to update"}), 400
    vals.append(meet_id)
    db.execute(f"UPDATE meetings SET {', '.join(sets)} WHERE id = ?", vals)
    db.commit()
    return jsonify({"ok": True})

@app.route('/api/meetings/<int:meet_id>', methods=['DELETE'])
def delete_meeting(meet_id):
    db = get_db()
    db.execute("DELETE FROM meetings WHERE id = ?", (meet_id,))
    db.commit()
    return jsonify({"ok": True})

# --- Contacts API ---

@app.route('/api/contacts', methods=['GET'])
def list_contacts():
    db = get_db()
    rows = db.execute("SELECT * FROM contacts ORDER BY name").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/contacts', methods=['POST'])
def create_contact():
    data = request.get_json()
    db = get_db()
    cursor = db.execute(
        "INSERT INTO contacts (name, relationship, company, last_contact_date, notes) VALUES (?, ?, ?, ?, ?)",
        (data['name'], data.get('relationship', 'other'), data.get('company', ''), data.get('last_contact_date'), data.get('notes', ''))
    )
    db.commit()
    return jsonify({"id": cursor.lastrowid}), 201

@app.route('/api/contacts/<int:contact_id>', methods=['PUT'])
def update_contact(contact_id):
    data = request.get_json()
    db = get_db()
    sets, vals = [], []
    for k in ('name', 'relationship', 'company', 'last_contact_date', 'notes'):
        if k in data:
            sets.append(f"{k} = ?")
            vals.append(data[k])
    if not sets:
        return jsonify({"error": "No fields to update"}), 400
    vals.append(contact_id)
    db.execute(f"UPDATE contacts SET {', '.join(sets)} WHERE id = ?", vals)
    db.commit()
    return jsonify({"ok": True})

@app.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    db = get_db()
    db.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    db.commit()
    return jsonify({"ok": True})

# --- Daily Log API ---

@app.route('/api/daily-log', methods=['GET'])
def list_daily_logs():
    db = get_db()
    rows = db.execute("SELECT * FROM daily_log ORDER BY date DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/daily-log/<date>', methods=['GET'])
def get_daily_log(date):
    db = get_db()
    row = db.execute("SELECT * FROM daily_log WHERE date = ?", (date,)).fetchone()
    if not row:
        return jsonify({"date": date, "notes": ""})
    return jsonify(dict(row))

@app.route('/api/daily-log', methods=['POST'])
def upsert_daily_log():
    data = request.get_json()
    db = get_db()
    db.execute("INSERT INTO daily_log (date, notes) VALUES (?, ?) ON CONFLICT(date) DO UPDATE SET notes = ?",
               (data['date'], data.get('notes', ''), data.get('notes', '')))
    db.commit()
    return jsonify({"ok": True})

# --- Heatmap API ---

@app.route('/api/heatmap')
def heatmap():
    year = request.args.get('year', str(datetime.now().year))
    db = get_db()
    counts = {}
    # applications
    for r in db.execute("SELECT date_applied, COUNT(*) as c FROM applications WHERE strftime('%Y', date_applied)=? GROUP BY date_applied", (year,)).fetchall():
        counts[r['date_applied']] = counts.get(r['date_applied'], 0) + r['c']
    # interviews
    for r in db.execute("SELECT date, COUNT(*) as c FROM interviews WHERE strftime('%Y', date)=? GROUP BY date", (year,)).fetchall():
        counts[r['date']] = counts.get(r['date'], 0) + r['c']
    # tasks completed
    for r in db.execute("SELECT date(updated_at) as d, COUNT(*) as c FROM tasks WHERE status='done' AND strftime('%Y', updated_at)=? GROUP BY d", (year,)).fetchall():
        counts[r['d']] = counts.get(r['d'], 0) + r['c']
    # meetings
    for r in db.execute("SELECT date, COUNT(*) as c FROM meetings WHERE strftime('%Y', date)=? GROUP BY date", (year,)).fetchall():
        counts[r['date']] = counts.get(r['date'], 0) + r['c']
    # projects
    for r in db.execute("SELECT date(last_updated) as d, COUNT(*) as c FROM projects WHERE strftime('%Y', last_updated)=? GROUP BY d", (year,)).fetchall():
        counts[r['d']] = counts.get(r['d'], 0) + r['c']
    # convert keys to string dates
    return jsonify({k: v for k, v in counts.items() if k})

# --- Report API ---

@app.route('/api/report', methods=['POST'])
def generate_report():
    data = request.get_json()
    start = data['start_date']
    end = data['end_date']
    modules = data.get('modules', ['applications', 'tasks', 'meetings', 'projects'])
    db = get_db()
    stats = {}
    if 'applications' in modules:
        stats['applications_sent'] = db.execute("SELECT COUNT(*) as c FROM applications WHERE date_applied BETWEEN ? AND ?", (start, end)).fetchone()['c']
    if 'applications' in modules or 'interviews' in modules:
        stats['interviews'] = db.execute("SELECT COUNT(*) as c FROM interviews WHERE date BETWEEN ? AND ?", (start, end)).fetchone()['c']
    if 'tasks' in modules:
        done = db.execute("SELECT COUNT(*) as c FROM tasks WHERE status='done' AND date(updated_at) BETWEEN ? AND ?", (start, end)).fetchone()['c']
        total = db.execute("SELECT COUNT(*) as c FROM tasks").fetchone()['c']
        stats['tasks_completed'] = done
        stats['tasks_total'] = total
    if 'meetings' in modules:
        stats['meetings'] = db.execute("SELECT COUNT(*) as c FROM meetings WHERE date BETWEEN ? AND ?", (start, end)).fetchone()['c']
    if 'projects' in modules:
        stats['active_projects'] = db.execute("SELECT COUNT(*) as c FROM projects WHERE status='active'").fetchone()['c']
    # Try Ollama summary
    summary = ""
    try:
        prompt = f"You are a personal productivity assistant. Summarize this activity data in 3-4 sentences, highlighting wins and patterns.\n\nPeriod: {start} to {end}\nApplications sent: {stats.get('applications_sent',0)}\nInterviews: {stats.get('interviews',0)}\nTasks completed: {stats.get('tasks_completed',0)} / {stats.get('tasks_total',0)}\nMeetings: {stats.get('meetings',0)}\nActive projects: {stats.get('active_projects',0)}\n\nKeep it concise and motivating."
        result = subprocess.run(["ollama", "run", "minimax-m2.7:cloud"], input=prompt, capture_output=True, text=True, timeout=60)
        summary = result.stdout.strip()
    except Exception:
        summary = f"Report generated for {start} to {end}. " + ", ".join(f"{k}: {v}" for k, v in stats.items()) + "."
    return jsonify({"summary": summary, "stats": stats, "generated_at": datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(port=5001, debug=True)