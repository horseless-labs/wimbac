import sqlite3
import csv
import os

# Paths relative to the script
DATA_DIR = "data/raw/gtfs"
DB_PATH = "gtfs_static.db"

def build_db():
    # Connect (this creates the file if it doesn't exist)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("--- Creating Tables ---")
    # We only need trip_id, stop_sequence, and stop_id for the gap-filler
    cursor.execute("DROP TABLE IF EXISTS stop_times")
    cursor.execute("""
        CREATE TABLE stop_times (
            trip_id TEXT,
            stop_sequence INTEGER,
            stop_id TEXT
        )
    """)

    cursor.execute("DROP TABLE IF EXISTS stops")
    cursor.execute("""
        CREATE TABLE stops (
            stop_id TEXT PRIMARY KEY,
            stop_name TEXT,
            stop_lat REAL,
            stop_lon REAL
        )
    """)

    # 1. Populate stop_times (The big one)
    stop_times_file = os.path.join(DATA_DIR, "stop_times.txt")
    print(f"--- Loading {stop_times_file} ---")
    
    with open(stop_times_file, 'r') as f:
        reader = csv.DictReader(f)
        # We use a generator to keep memory usage low during the read
        batch = ((row['trip_id'], int(row['stop_sequence']), row['stop_id']) for row in reader)
        
        # executemany is WAY faster than individual inserts
        cursor.executemany(
            "INSERT INTO stop_times (trip_id, stop_sequence, stop_id) VALUES (?, ?, ?)", 
            batch
        )

    # 2. Populate stops
    stops_file = os.path.join(DATA_DIR, "stops.txt")
    print(f"--- Loading {stops_file} ---")
    
    with open(stops_file, 'r') as f:
        reader = csv.DictReader(f)
        batch = ((row['stop_id'], row['stop_name'], float(row['stop_lat']), float(row['stop_lon'])) for row in reader)
        cursor.executemany(
            "INSERT INTO stops (stop_id, stop_name, stop_lat, stop_lon) VALUES (?, ?, ?, ?)", 
            batch
        )

    print("--- Creating Indexes (The Performance Magic) ---")
    # This index makes "Give me all stops for Trip X" take microseconds
    cursor.execute("CREATE INDEX idx_trip_seq ON stop_times (trip_id, stop_sequence)")
    
    conn.commit()
    conn.close()
    print(f"Done! Database created at {DB_PATH}")

if __name__ == "__main__":
    build_db()