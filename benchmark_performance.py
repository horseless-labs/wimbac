import os
import sys
import csv
import sqlite3
import psutil
import gc
import time

# Config
DATA_PATH = "data/raw/gtfs/stop_times.txt"
DB_PATH = "gtfs_static.db"

def get_stats():
    """Returns (RSS Memory in MB, Total CPU Time in Seconds)."""
    proc = psutil.Process(os.getpid())
    mem = proc.memory_info().rss / (1024 * 1024)
    cpu_times = proc.cpu_times()
    # User time + System time = Total time the CPU worked on this process
    total_cpu = cpu_times.user + cpu_times.system
    return mem, total_cpu

def benchmark_naive_dict():
    data = {}
    with open(DATA_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tid = row['trip_id']
            sid = row['stop_id']
            if tid not in data:
                data[tid] = []
            data[tid].append(sid)
    return data

def benchmark_optimized_tuple():
    data = {}
    with open(DATA_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tid = int(row['trip_id'])
            sid = int(row['stop_id'])
            if tid not in data:
                data[tid] = []
            data[tid].append(sid)
    for tid in data:
        data[tid] = tuple(data[tid])
    return data

def benchmark_sqlite():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # We simulate 1000 random lookups to show "Work" 
    # otherwise SQLite start-up is too fast to measure
    for _ in range(1000):
        cursor.execute("SELECT stop_id FROM stop_times WHERE trip_id = '18957054'")
        _ = cursor.fetchall()
    conn.close()

def run_test(name, func):
    print(f"\n--- {name} ---")
    gc.collect()
    
    start_mem, start_cpu = get_stats()
    start_wall = time.time()
    
    result = func()
    
    end_wall = time.time()
    end_mem, end_cpu = get_stats()
    
    print(f"Wall Clock Time: {end_wall - start_wall:.4f} s")
    print(f"CPU Time Used:   {end_cpu - start_cpu:.4f} s")
    print(f"Memory Delta:    {end_mem - start_mem:.2f} MB")
    
    del result # Clear for next test
    gc.collect()

if __name__ == "__main__":
    if not os.path.exists(DATA_PATH) or not os.path.exists(DB_PATH):
        print("Ensure stop_times.txt and gtfs_static.db exist.")
        sys.exit(1)

    run_test("Method 1: Naive Dictionary", benchmark_naive_dict)
    run_test("Method 2: Optimized Tuple", benchmark_optimized_tuple)
    run_test("Method 3: SQLite (1,000 Lookups)", benchmark_sqlite)