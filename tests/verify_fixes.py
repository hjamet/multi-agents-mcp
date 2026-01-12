import sys
import os
import json
import time

# Fix path: Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.core.logic import Engine
from src.core.state import StateStore

def test_history_delta():
    print("--- Testing History Delta Logic ---")
    
    # 1. Setup Mock State
    store = StateStore()
    
    # Reset State for test
    def reset(s):
        s["agents"] = {
            "Alice": {"status": "connected", "profile_ref": "Agent"},
            "Bob": {"status": "connected", "profile_ref": "Agent"}
        }
        s["config"] = {"profiles": [{"name": "Agent", "connections": [], "capabilities": ["public", "private", "audience", "open"]}]}
        s["messages"] = []
        s["turn"] = {"current": "Alice", "next": None}
        return "Reset"
    store.update(reset)
    
    engine = Engine(store)
    
    # 2. Simulate Conversation
    # Alice speaks (Index 0)
    engine.post_message("Alice", "Hello Bob", True, "Bob", [])
    
    # Bob speaks (Index 1)
    # Check Bob's view BEFORE he speaks (should see Alice's message)
    # Actually logic.py checks turn. turn is Bob now.
    
    res = engine.wait_for_turn("Bob", timeout_seconds=1)
    if res["status"] != "success":
        print("FAIL: Bob did not get turn")
        return
        
    hist = res["messages"]
    print(f"Bob sees {len(hist)} messages (Expected 1)")
    # Should see Alice's message because Bob hasn't spoken yet (last_my_index = -1 -> slice 0)
    assert len(hist) == 1
    assert hist[0]["content"] == "Hello Bob"
    
    # Bob replies (Index 1)
    engine.post_message("Bob", "Hi Alice", True, "Alice", [])
    
    # Alice speaks again (Index 2)
    # Alice turn
    res = engine.wait_for_turn("Alice", timeout_seconds=1)
    hist = res["messages"]
    print(f"Alice sees {len(hist)} messages (Expected 1)")
    
    # LAST TIME Alice spoke was Index 0.
    # Current History:
    # 0: Alice "Hello Bob"
    # 1: Bob "Hi Alice"
    # Alice should see messages AFTER Index 0 -> Index 1 onwards.
    # So she should see only Bob's message.
    
    assert len(hist) == 1
    assert hist[0]["content"] == "Hi Alice"
    
    # Alice replies (Index 2)
    engine.post_message("Alice", "How are you?", True, "Bob", [])
    
    # Bob speaks again
    res = engine.wait_for_turn("Bob", timeout_seconds=1)
    hist = res["messages"]
    # Last time Bob spoke was Index 1.
    # Current History:
    # 0: Alice
    # 1: Bob
    # 2: Alice
    # Bob should see messages AFTER Index 1 -> Index 2 onwards.
    print(f"Bob sees {len(hist)} messages (Expected 1)")
    assert len(hist) == 1
    assert hist[0]["content"] == "How are you?"

    print("PASS: History Delta Delta logic works.")

def test_visibility():
    print("\n--- Testing Visibility Logic ---")
    store = StateStore() # Reset implicit
    
    def reset(s):
        s["agents"] = {
            "Alice": {"status": "connected"},
            "Bob": {"status": "connected"},
            "Charlie": {"status": "connected"}
        }
        s["messages"] = []
        s["turn"] = {"current": "Charlie", "next": None}
        return "Reset"
    store.update(reset)
    
    engine = Engine(store)
    
    # Alice sends Private to Bob (Index 0)
    # Alice is not active turn, but we inject message manually to simulate history
    def inject(s):
        s["messages"].append({
            "from": "Alice", "content": "Secret for Bob", "public": False, "target": "Bob", "audience": []
        })
        s["messages"].append({
            "from": "Alice", "content": "Public for All", "public": True, "target": "Bob", "audience": []
        })
        return "Injected"
    store.update(inject)
    
    # Charlie's Turn. Charlie hasn't spoken. Should see all PUBLIC messages.
    res = engine.wait_for_turn("Charlie", timeout_seconds=1)
    hist = res["messages"]
    
    print("Charlie's View:")
    for m in hist:
        print(f"- {m['properties'] if 'properties' in m else ''} {m['content']} (Pub: {m.get('public')})")
        
    # Charlie should see "Public for All" (Index 1)
    # Charlie should NOT see "Secret for Bob" (Index 0)
    
    assert len(hist) == 1
    assert hist[0]["content"] == "Public for All"
    
    print("PASS: Visibility logic works.")

if __name__ == "__main__":
    test_history_delta()
    test_visibility()
