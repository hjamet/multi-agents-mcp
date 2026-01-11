import multiprocessing
import time
import sys
import os
import shutil

# Setup path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.core.state import StateStore

STATE_FILE = "state_test_concurrency.json"

def worker(agent_name: str, count: int):
    store = StateStore(file_path=STATE_FILE)
    for i in range(count):
        def update_func(state):
            # Read
            msgs = state.get("messages", [])
            # Write
            msgs.append(f"{agent_name}-{i}")
            state["messages"] = msgs
            # Modify counter
            c = state.get("counter", 0)
            state["counter"] = c + 1
            return c + 1
            
        store.update(update_func)
        time.sleep(0.01)

def test_locking():
    # Reset
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
    
    num_processes = 4
    updates_per_process = 50
    expected_total = num_processes * updates_per_process
    
    processes = []
    print(f"Starting {num_processes} processes with {updates_per_process} updates each...")
    
    for i in range(num_processes):
        p = multiprocessing.Process(target=worker, args=(f"Agent{i}", updates_per_process))
        processes.append(p)
        p.start()
        
    for p in processes:
        p.join()
        
    # Verify
    store = StateStore(file_path=STATE_FILE)
    data = store.load()
    counter = data.get("counter", 0)
    messages = data.get("messages", [])
    
    print(f"Final Counter: {counter}")
    print(f"Expected: {expected_total}")
    print(f"Messages count: {len(messages)}")
    
    if counter == expected_total and len(messages) == expected_total:
        print("✅ SUCCESS: No race conditions detected.")
    else:
        print("❌ FAILURE: Race condition detected!")

if __name__ == "__main__":
    test_locking()
