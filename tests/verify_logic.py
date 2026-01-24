
import sys
import os
import json
import tempfile
import time

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from src.core.logic import Engine
    from src.core.state import StateStore
    import portalocker
except ImportError as e:
    print(f"SKIP: Missing dependencies for logic compliance verification: {e}")
    sys.exit(0)

def verify_logic_compliance():
    print("--- Verifying Core Logic Compliance ---")
    
    # 1. Setup Temp State
    f, path = tempfile.mkstemp()
    os.close(f)
    
    state_data = {
        "messages": [],
        "conversation_id": "unit-test-logic",
        "turn": {"current": "Agent1", "next": None},
        "agents": {
             "Agent1": {"status": "connected", "role": "R1", "profile_ref": "P1"},
             "Agent2": {"status": "connected", "role": "R2", "profile_ref": "P1"},
             "Agent3": {"status": "connected", "role": "R3", "profile_ref": "P1"}
        },
        "config": {
            "total_agents": 3,
            "profiles": [
                {"name": "P1", "capabilities": ["public", "private", "turn", "open", "audience"], "connections": [
                    {"target":"P1", "context":"peer"},
                    {"target":"User", "context":"admin"}
                ]}
            ]
        }
    }
    
    with open(path, "w") as f:
        json.dump(state_data, f)
        
    store = StateStore(path)
    engine = Engine(store)
    
    # 2. Test Private Message Visibility
    print("Test 1: Private Message Visibility (A1 -> A2)...", end=" ")
    engine.post_message("Agent1", "Secret A1->A2 @Agent2", False)
    
    data = store.load()
    if not data["messages"]:
        print("FAILED: No message posted")
        return
    msg = data["messages"][-1]
    
    # Manual Visibility Check logic from server/logic
    # Visible = Public OR (Private AND (To Me OR From Me OR In Audience OR Mentioned))
    def is_visible(m, me):
        if m.get("public"): return True
        if m.get("from") == me: return True
        if m.get("target") == me: return True # Target is often "Queue" now
        if me in (m.get("mentions") or []): return True
        if me in (m.get("audience") or []): return True
        return False
        
    assert is_visible(msg, "Agent1") == True
    assert is_visible(msg, "Agent2") == True
    assert is_visible(msg, "Agent3") == False
    print("PASSED")
    
    # 3. Test User Interaction Bypass
    print("Test 3: User Interaction (A2 -> User)...", end=" ")
    # Ensure Agent2 has turn
    def set_turn_a2(s):
        s["turn"]["current"] = "Agent2"
        return "Set turn A2"
    store.update(set_turn_a2)
    
    res = engine.post_message("Agent2", "Help @User", True)
    print(f"DEBUG RES: {res}", file=sys.stderr)
    assert "Turn passed to User" in res
    
    # Verify Turn did change
    data = store.load()
    assert data["turn"]["current"] == "User"
    print("PASSED")
    
    # Cleanup
    os.remove(path)
    print("--- ALL LOGIC CHECKS PASSED ---")

if __name__ == "__main__":
    verify_logic_compliance()
