from flask import Flask, jsonify, request, render_template
from db import init_db, get_db

app = Flask(__name__)
init_db()

MODULES = ["applications", "interviews", "tasks", "projects", "meetings", "contacts"]

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

if __name__ == '__main__':
    app.run(port=5001, debug=True)