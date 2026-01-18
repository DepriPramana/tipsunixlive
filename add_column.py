
import sqlite3
import os

DB_PATH = "./data.db"

def add_column():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(live_sessions)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "music_playlist_id" in columns:
            print("Column 'music_playlist_id' already exists in 'live_sessions'")
        else:
            print("Adding 'music_playlist_id' column to 'live_sessions'...")
            cursor.execute("ALTER TABLE live_sessions ADD COLUMN music_playlist_id INTEGER REFERENCES music_playlists(id)")
            conn.commit()
            print("Column added successfully!")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_column()
