import sqlite3
import os

db_path = 'data.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    columns_to_add = [
        ('latency_mode', "VARCHAR DEFAULT 'normal'"),
        ('enable_dvr', "BOOLEAN DEFAULT 1"),
        ('made_for_kids', "BOOLEAN DEFAULT 0"),
        ('category_id', "VARCHAR DEFAULT '24'"),
        ('thumbnail_url', "VARCHAR")
    ]
    
    for col_name, col_def in columns_to_add:
        try:
            cursor.execute(f'ALTER TABLE youtube_broadcasts ADD COLUMN {col_name} {col_def}')
            print(f'DONE: Column {col_name} added to youtube_broadcasts')
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f'INFO: Column {col_name} already exists')
            else:
                print(f'ERROR adding {col_name}: {e}')
    
    conn.commit()
    conn.close()
    print('Migration completed.')
else:
    print('ERROR: Database data.db not found')
