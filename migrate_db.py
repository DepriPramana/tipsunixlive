import sqlite3
import os

def migrate():
    db_path = 'd:/Source/streamlive/data.db'
    if not os.path.exists(db_path):
        # Fallback for Linux if path differs, or use relative
        db_path = 'data.db'
        
    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    tables_to_update = {
        'live_history': 'max_duration_hours',
        'scheduled_lives': 'max_duration_hours'
    }
    
    for table, column in tables_to_update.items():
        try:
            print(f"Adding column '{column}' to table '{table}'...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} INTEGER DEFAULT 0;")
            print(f"Successfully updated {table}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"Column '{column}' already exists in {table}, skipping.")
            else:
                print(f"Error updating {table}: {e}")
                
    conn.commit()
    conn.close()
    print("Migration completed.")

if __name__ == "__main__":
    migrate()
