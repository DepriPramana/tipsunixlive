
import sqlite3
import os
import sys

def run_migration(sql_file_path):
    # Detect database path
    db_path = 'data.db'
    if not os.path.exists(db_path):
        # Check standard deployment paths
        possible_paths = [
            'd:/Source/streamlive/data.db', # Local Dev
            '/home/antigravity/streamlive/data.db', # Potential cloud path
            '/var/www/streamlive/data.db'
        ]
        for p in possible_paths:
            if os.path.exists(p):
                db_path = p
                break
    
    if not os.path.exists(db_path):
        print(f"❌ Error: Database file not found at {db_path}")
        sys.exit(1)
        
    print(f"📂 Database: {db_path}")
    print(f"📜 Migration file: {sql_file_path}")
    
    if not os.path.exists(sql_file_path):
        # Convert relative to absolute
        abs_path = os.path.abspath(sql_file_path)
        if not os.path.exists(abs_path):
            print(f"❌ Error: Migration file not found: {sql_file_path}")
            sys.exit(1)
        sql_file_path = abs_path

    try:
        # Read SQL file
        with open(sql_file_path, 'r') as f:
            sql_script = f.read()
            
        # Connect to DB
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Execute script
        print("🚀 Executing migration...")
        cursor.executescript(sql_script)
        
        conn.commit()
        conn.close()
        
        print("✅ Migration applied successfully!")
        
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("⚠️  Warning: Column likely already exists (duplicate column name).")
            print("   Migration considered successful (nothing to do).")
        else:
            print(f"❌ Database error: {e}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_migration.py <path_to_sql_file>")
        print("Example: python run_migration.py migrations/add_new_column.sql")
        sys.exit(1)
        
    run_migration(sys.argv[1])
