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

if __name__ == '__main__':
    app.run(port=5001, debug=True)