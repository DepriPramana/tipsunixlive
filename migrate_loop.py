import sqlite3
import os

db_path = 'data.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute('ALTER TABLE live_sessions ADD COLUMN loop BOOLEAN DEFAULT 1 NOT NULL')
        conn.commit()
        print('DONE: Column loop added to live_sessions')
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print('INFO: Column loop already exists')
        else:
            print(f'ERROR: {e}')
    finally:
        conn.close()
else:
    print('ERROR: Database data.db not found')
