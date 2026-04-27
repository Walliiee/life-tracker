import os
import sys
import sqlite3
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

SCHEMA = os.path.join(os.path.dirname(__file__), '..', 'schema.sql')


@pytest.fixture()
def client(tmp_path):
    import db
    db.DB_PATH = str(tmp_path / 'test.db')
    conn = sqlite3.connect(db.DB_PATH)
    with open(SCHEMA) as f:
        conn.executescript(f.read())
    conn.close()

    import app as app_mod
    app_mod.app.config['TESTING'] = True
    with app_mod.app.test_client() as c:
        yield c
