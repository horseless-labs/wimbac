import os
import sys
import csv
import sqlite3
import psutil
import gc

# Config
DATA_PATH = "data/raw/gtfs/stop_times.txt"
DB_PATH = "gtfs_static.db"

def get_memory_usage():
    """Returns the current RSS memory usage in Megabytes."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def benchmark_naive_dict():
    print("\n--- Method 1: Naive Dictionary (Strings) ---")
    start_mem = get_memory_usage()
    
    data = {}
    with open(DATA_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tid = row['trip_id']
            sid = row['stop_id']
            if tid not in data:
                data[tid] = []
            data[tid].append(sid)
            
    end_mem = get_memory_usage()
    print(f"Memory Used: {end_mem - start_mem:.2f} MB")
    return data

def benchmark_optimized_tuple():
    print("\n--- Method 2: Optimized (Int Mapping + Tuples) ---")
    start_mem = get_memory_usage()
    
    data = {}
    with open(DATA_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Converting to int saves massive space vs strings
            tid = int(row['trip_id'])
            sid = int(row['stop_id'])
            if tid not in data:
                data[tid] = []
            data[tid].append(sid)
    
    # Convert lists to tuples to lock them in memory
    for tid in data:
        data[tid] = tuple(data[tid])
            
    end_mem = get_memory_usage()
    print(f"Memory Used: {end_mem - start_mem:.2f} MB")
    return data

def benchmark_sqlite():
    print("\n--- Method 3: SQLite (Disk-Backed) ---")
    start_mem = get_memory_usage()
    
    # Connect and perform a sample query to 'warm' the connection
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT stop_id FROM stop_times WHERE trip_id = '18957054'")
    _ = cursor.fetchall()
    
    end_mem = get_memory_usage()
    print(f"Memory Used: {end_mem - start_mem:.2f} MB")
    conn.close()

if __name__ == "__main__":
    if not os.path.exists(DATA_PATH):
        print(f"Error: CSV not found at {DATA_PATH}")
        sys.exit(1)

    print(f"Initial Process Memory: {get_memory_usage():.2f} MB")

    # We run these one by one and clear memory in between
    # to keep the benchmarks clean.
    
    d1 = benchmark_naive_dict()
    del d1
    gc.collect() # Force garbage collection
    
    d2 = benchmark_optimized_tuple()
    del d2
    gc.collect()
    
    benchmark_sqlite()