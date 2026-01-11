import threading
import time
import sys
import os
import shutil

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.core.logic import Engine
from src.core.state import StateStore

STATE_FILE = "state_test_game.json"

def agent_lifecycle(name: str, engine: Engine, behavior: list):
    """
    Simulates an agent's lifecycle:
    1. Register/Handshake
    2. Execute behavior list [(action, params), ...]
    """
    print(f"[{name}] Lifecycle START")
    
    # 1. Handshake
    while True:
        info = engine.register_agent(name)
        if info["ready"]:
            print(f"[{name}] Connected & Ready! Role: {info['role']}")
            break
        time.sleep(1)
        
    # 2. Loop
    for action, params in behavior:
        if action == "talk":
            # Simulate Talk Tool
            print(f"[{name}] Talking -> Next: {params['next']}")
            engine.post_message(name, params["msg"], True, params["next"], [])
            
            # Simulate Wait Tool (Smart Block)
            print(f"[{name}] Waiting for turn...")
            while True:
                res = engine.wait_for_turn(name, timeout_seconds=2)
                if res["status"] == "success":
                    print(f"[{name}] My turn! Got {len(res['messages'])} msgs.")
                    break
                # Loop because timeout
                
        elif action == "wait":
             # Simulate Wait Tool (Smart Block) without talking first (e.g. second player)
            print(f"[{name}] Waiting for turn...")
            while True:
                res = engine.wait_for_turn(name, timeout_seconds=2)
                if res["status"] == "success":
                    print(f"[{name}] My turn! Got {len(res['messages'])} msgs.")
                    break

    print(f"[{name}] Lifecycle END")

def test_game_loop():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
    
    store = StateStore(file_path=STATE_FILE)
    engine = Engine(store)
    
    # Setup Logic:
    # A starts.
    # A talks to B.
    # B talks to C.
    # C starts -> End.
    
    # Behaviors:
    # A: Talk(next=B) -> Wait -> End
    # B: Wait -> Talk(next=C) -> End
    # C: Wait -> Talk(next=A) -> End
    
    # Note: Someone needs to kickstart the turn.
    # Logic in Engine doesn't auto-set first turn?
    # Engine.register_agent doesn't set turn.
    # We need to manually inject the first turn or have a rule.
    # Let's say we manually set turn to "AgentA" in state for test.
    
    store.update(lambda s: s.setdefault("turn", {}).update({"current": "AgentA"}))
    store.update(lambda s: s.setdefault("config", {}).update({"total_agents": 3}))

    threads = []
    
    b_agent_a = [
        ("talk", {"msg": "Hello form A", "next": "AgentB"}),
        ("wait", {}) # Waits for C to pass back to A
    ]
    b_agent_b = [
        ("wait", {}),
        ("talk", {"msg": "Hello from B", "next": "AgentC"})
    ]
    b_agent_c = [
        ("wait", {}),
        ("talk", {"msg": "Hello from C", "next": "AgentA"})
    ]

    t_a = threading.Thread(target=agent_lifecycle, args=("AgentA", engine, b_agent_a))
    t_b = threading.Thread(target=agent_lifecycle, args=("AgentB", engine, b_agent_b))
    t_c = threading.Thread(target=agent_lifecycle, args=("AgentC", engine, b_agent_c))
    
    threads = [t_a, t_b, t_c]
    
    print("Starting Threads...")
    for t in threads: t.start()
    
    for t in threads: t.join(timeout=10)
    
    # Check if all finished
    alive = [t.is_alive() for t in threads]
    if any(alive):
        print("❌ FAILURE: threads timed out / deadlocked.")
    else:
        print("✅ SUCCESS: Game loop completed.")

if __name__ == "__main__":
    test_game_loop()
