
import sqlite3
import os

DB_PATH = "./data.db"

def migrate_db():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(music_playlists)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "sound_effect_path" not in columns:
            print("Adding 'sound_effect_path' column...")
            cursor.execute("ALTER TABLE music_playlists ADD COLUMN sound_effect_path VARCHAR")
        else:
            print("'sound_effect_path' already exists")
            
        if "sound_effect_volume" not in columns:
            print("Adding 'sound_effect_volume' column...")
            cursor.execute("ALTER TABLE music_playlists ADD COLUMN sound_effect_volume FLOAT DEFAULT 0.3 NOT NULL")
        else:
            print("'sound_effect_volume' already exists")

        conn.commit()
        print("Migration successful!")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db()
