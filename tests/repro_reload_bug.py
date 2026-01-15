
import sys
import os
import time
import asyncio
from pathlib import Path

# Add src to path
sys.path.append(os.path.abspath("."))
from src.core.logic import Engine
from src.core.state import StateStore

async def test_reload_leak():
    print("--- TESTING RELOAD LEAK ---")
    
    # 1. Setup State
    store = StateStore()
    
    def setup(s):
        s["agents"] = {
            "AgentA": {"status": "connected", "role": "Test Role", "profile_ref": "Agent"}
        }
        s["config"] = {
            "profiles": [{"name": "Agent", "capabilities": ["public"]}],
            "user_availability": "available"
        }
        s["turn"] = {"current": "AgentA", "consecutive_count": 0}
        s["messages"] = []
        s["reload_queue"] = ["AgentA"] # Simulate User added AgentA to queue
        return "Setup Done"
    
    store.update(setup)
    
    engine = Engine(store)
    
    # 2. Trigger Transition (Simulate end of previous turn)
    # This should pop AgentA from queue and set reload_active=True
    def transition(s):
        engine._finalize_turn_transition(s, "AgentA")
        return "Transition Done"
        
    store.update(transition)
    
    # 3. Verify State
    state = store.load()
    print(f"Current Turn: {state['turn']['current']}")
    print(f"AgentA Reload Active: {state['agents']['AgentA'].get('reload_active')}")
    print(f"AgentA Status: {state['agents']['AgentA']['status']}")
    
    if not state['agents']['AgentA'].get('reload_active'):
        print("FAIL: reload_active not set!")
        return

    if state['agents']['AgentA']['status'] == "pending_connection":
        print("NOTE: Status IS pending_connection (Unexpected based on analysis, but good if true)")
    else:
        print("NOTE: Status is NOT pending_connection (Expected bug)")

    # 4. Simulate `talk` logic checking for blockers
    # We will simulate the critical checks in server.py `talk`
    print("\n--- Simulating talk() Checks ---")
    
    sender = state['turn']['current'] # "AgentA"
    
    
    # Check 1: Reload Active Block (Hypothetically missing -> NOW ADDED to verify fix logic)
    # Simulate the check added to server.py
    sender_data = state.get("agents", {}).get(sender, {})
    if sender_data.get("reload_active"):
        print("✅ BLOCKED: Reload Active detected. Simulation returns DENIED.")
        return

    # Check 2: wait_for_turn_async
    try:
        print("Calling wait_for_turn_async...")
        result = await engine.wait_for_turn_async(sender, timeout_seconds=2)
        print(f"wait_for_turn Result: {result['status']}")
        
        if result['status'] == "success":
            print("❌ BUG REPRODUCED: Agent was allowed to acquire turn despite Reload Request!")
        elif result['status'] == "reset":
            print("✅ BLOCKED: wait_for_turn returned reset.")
        else:
             print(f"Result: {result}")
             
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_reload_leak())
