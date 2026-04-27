import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_app(client, **kwargs):
    return client.post('/api/applications', json={
        'company': kwargs.get('company', 'Acme'),
        'role': kwargs.get('role', 'Engineer'),
        'date_applied': kwargs.get('date_applied', '2024-01-15'),
    })


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def test_status(client):
    r = client.get('/api/status')
    assert r.status_code == 200
    assert r.json['status'] == 'ok'


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

def test_create_application(client):
    r = make_app(client)
    assert r.status_code == 201
    assert 'id' in r.json


def test_create_application_missing_fields(client):
    r = client.post('/api/applications', json={'company': 'Acme'})
    assert r.status_code == 400
    assert 'Missing required fields' in r.json['error']


def test_create_application_bad_date(client):
    r = client.post('/api/applications', json={
        'company': 'Acme', 'role': 'Eng', 'date_applied': '15-01-2024'
    })
    assert r.status_code == 400
    assert 'YYYY-MM-DD' in r.json['error']


def test_create_application_bad_status(client):
    r = client.post('/api/applications', json={
        'company': 'Acme', 'role': 'Eng', 'date_applied': '2024-01-01', 'status': 'maybe'
    })
    assert r.status_code == 400


def test_list_applications(client):
    make_app(client)
    r = client.get('/api/applications')
    assert r.status_code == 200
    assert len(r.json) >= 1


def test_update_application(client):
    app_id = make_app(client).json['id']
    r = client.put(f'/api/applications/{app_id}', json={'status': 'interview'})
    assert r.status_code == 200
    assert r.json['ok'] is True


def test_update_application_no_fields(client):
    app_id = make_app(client).json['id']
    r = client.put(f'/api/applications/{app_id}', json={})
    assert r.status_code == 400


def test_delete_application(client):
    app_id = make_app(client).json['id']
    r = client.delete(f'/api/applications/{app_id}')
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Interviews
# ---------------------------------------------------------------------------

def test_create_interview(client):
    app_id = make_app(client).json['id']
    r = client.post('/api/interviews', json={
        'application_id': app_id, 'date': '2024-01-20', 'type': 'phone'
    })
    assert r.status_code == 201


def test_create_interview_missing_fields(client):
    r = client.post('/api/interviews', json={'date': '2024-01-20'})
    assert r.status_code == 400


def test_create_interview_bad_type(client):
    app_id = make_app(client).json['id']
    r = client.post('/api/interviews', json={
        'application_id': app_id, 'date': '2024-01-20', 'type': 'carrier_pigeon'
    })
    assert r.status_code == 400


def test_create_interview_bad_date(client):
    app_id = make_app(client).json['id']
    r = client.post('/api/interviews', json={
        'application_id': app_id, 'date': '20-01-2024', 'type': 'video'
    })
    assert r.status_code == 400


def test_list_interviews(client):
    r = client.get('/api/interviews')
    assert r.status_code == 200
    assert isinstance(r.json, list)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def test_create_task(client):
    r = client.post('/api/tasks', json={'title': 'Write tests'})
    assert r.status_code == 201


def test_create_task_missing_title(client):
    r = client.post('/api/tasks', json={})
    assert r.status_code == 400


def test_create_task_bad_priority(client):
    r = client.post('/api/tasks', json={'title': 'Task', 'priority': 'urgent'})
    assert r.status_code == 400


def test_create_task_bad_status(client):
    r = client.post('/api/tasks', json={'title': 'Task', 'status': 'blocked'})
    assert r.status_code == 400


def test_create_task_bad_due_date(client):
    r = client.post('/api/tasks', json={'title': 'Task', 'due_date': 'tomorrow'})
    assert r.status_code == 400


def test_update_task_status(client):
    task_id = client.post('/api/tasks', json={'title': 'Task'}).json['id']
    r = client.put(f'/api/tasks/{task_id}', json={'status': 'done'})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def test_create_project(client):
    r = client.post('/api/projects', json={'name': 'My Project'})
    assert r.status_code == 201


def test_create_project_missing_name(client):
    r = client.post('/api/projects', json={})
    assert r.status_code == 400


def test_create_project_bad_type(client):
    r = client.post('/api/projects', json={'name': 'Proj', 'type': 'secret'})
    assert r.status_code == 400


def test_create_project_bad_status(client):
    r = client.post('/api/projects', json={'name': 'Proj', 'status': 'archived'})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

def test_create_contact(client):
    r = client.post('/api/contacts', json={'name': 'Alice'})
    assert r.status_code == 201


def test_create_contact_missing_name(client):
    r = client.post('/api/contacts', json={})
    assert r.status_code == 400


def test_create_contact_bad_relationship(client):
    r = client.post('/api/contacts', json={'name': 'Bob', 'relationship': 'nemesis'})
    assert r.status_code == 400


def test_create_contact_bad_date(client):
    r = client.post('/api/contacts', json={'name': 'Carol', 'last_contact_date': '01/01/2024'})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Meetings
# ---------------------------------------------------------------------------

def test_create_meeting(client):
    r = client.post('/api/meetings', json={'person_name': 'Dave', 'date': '2024-03-01'})
    assert r.status_code == 201
    assert 'contact_updated' in r.json


def test_meeting_updates_matching_contact(client):
    client.post('/api/contacts', json={'name': 'Eve'})
    r = client.post('/api/meetings', json={'person_name': 'Eve', 'date': '2024-03-15'})
    assert r.status_code == 201
    assert r.json['contact_updated'] is True


def test_meeting_no_contact_match(client):
    r = client.post('/api/meetings', json={'person_name': 'NoSuchPerson', 'date': '2024-03-15'})
    assert r.status_code == 201
    assert r.json['contact_updated'] is False


def test_create_meeting_missing_fields(client):
    r = client.post('/api/meetings', json={'person_name': 'Frank'})
    assert r.status_code == 400


def test_create_meeting_bad_date(client):
    r = client.post('/api/meetings', json={'person_name': 'Grace', 'date': 'next-tuesday'})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Daily log
# ---------------------------------------------------------------------------

def test_daily_log_upsert(client):
    r = client.post('/api/daily-log', json={'date': '2024-06-01', 'notes': 'Good day'})
    assert r.status_code == 200


def test_daily_log_get(client):
    client.post('/api/daily-log', json={'date': '2024-06-02', 'notes': 'Productive'})
    r = client.get('/api/daily-log/2024-06-02')
    assert r.status_code == 200
    assert r.json['notes'] == 'Productive'


def test_daily_log_get_missing(client):
    r = client.get('/api/daily-log/2099-01-01')
    assert r.status_code == 200
    assert r.json['notes'] == ''


def test_daily_log_bad_date(client):
    r = client.post('/api/daily-log', json={'date': 'not-a-date'})
    assert r.status_code == 400


def test_daily_log_missing_date(client):
    r = client.post('/api/daily-log', json={'notes': 'forgot the date'})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def test_search_empty_query(client):
    r = client.get('/api/search?q=')
    assert r.status_code == 200
    assert r.json['applications'] == []


def test_search_finds_application(client):
    make_app(client, company='SearchCorp')
    r = client.get('/api/search?q=searchcorp')
    assert r.status_code == 200
    assert any(a['company'] == 'SearchCorp' for a in r.json['applications'])


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def test_export(client):
    make_app(client)
    r = client.get('/api/export')
    assert r.status_code == 200
    assert 'exported_at' in r.json
    assert 'data' in r.json
    expected_tables = {'applications', 'interviews', 'tasks', 'projects', 'meetings', 'contacts', 'daily_log'}
    assert expected_tables <= set(r.json['data'].keys())
    assert len(r.json['data']['applications']) >= 1


# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------

def test_heatmap(client):
    r = client.get('/api/heatmap?year=2024')
    assert r.status_code == 200
    assert isinstance(r.json, dict)


def test_heatmap_bad_year(client):
    r = client.get('/api/heatmap?year=notayear')
    assert r.status_code == 400
