
import sys
import os
import json
import time

# Mock State
sys.path.append(os.getcwd())
from src.core.logic import Engine

def test_user_flow():
    print("--- Testing User Flow Integration ---")
    
    # 1. Setup Engine & State
    engine = Engine()
    
    # Reset State for test
    engine.state.file_path = "test_state_user.json"
    if os.path.exists("test_state_user.json"):
        os.remove("test_state_user.json")
        
    def init_state(s):
        s["agents"] = {
            "Agent1": {
                "role": "You are Agent 1", 
                "profile_ref": "Agent", 
                "status": "connected",
                "connections": [{"target": "User", "context": "Report to user"}]
            }
        }
        s["config"] = {
            "total_agents": 1, 
            "context": "Test Context",
            "profiles": [
                {"name": "Agent", "capabilities": ["public", "private", "open"], "connections": []}
            ]
        }
        s["turn"] = {"current": "Agent1"}
        return "Init Done"
        
    engine.state.update(init_state)
    
    # 2. Agent1 talks to User (Should NOT change turn)
    print("\n[Action] Agent1 talks to User...")
    res = engine.post_message(
        from_agent="Agent1",
        content="Hello User!",
        public=False,
        next_agent="User",
        audience=[]
    )
    print(f"Result: {res}")
    
    # Verify State
    data = engine.state.load()
    last_msg = data["messages"][-1]
    current_turn = data["turn"]["current"]
    
    assert last_msg["target"] == "User", "Target should be User"
    assert current_turn == "Agent1", f"Turn should remain Agent1, but is {current_turn}"
    
    # 3. User replies (Inject)
    print("\n[Action] User replies...")
    def user_reply(s):
        s["messages"].append({
            "from": "User",
            "content": "Good job.",
            "public": False,
            "target": "Agent1",
            "timestamp": time.time()
        })
        return "Replied"
    engine.state.update(user_reply)
    
    # 4. Agent1 talks to another agent (simulated, no other agent exists but logic should allow turn change attempt)
    # We need to add Agent2 for this test
    def add_agent2(s):
        s["agents"]["Agent2"] = {"profile_ref": "Agent", "status": "connected"}
        s["config"]["profiles"][0]["connections"].append({"target": "Agent", "context": "friend"}) 
        # Need to fix profile connection logic for the test to pass `check_target`
        # Or just use OPEN mode (Agent has 'open' cap)
        return "Added Agent2"
    engine.state.update(add_agent2)
    
    print("\n[Action] Agent1 passes turn to Agent2...")
    res = engine.post_message(
        from_agent="Agent1",
        content="I spoke to user.",
        public=True,
        next_agent="Agent2",
        audience=[]
    )
    print(f"Result: {res}")
    
    data = engine.state.load()
    current_turn = data["turn"]["current"]
    assert current_turn == "Agent2", f"Turn should be Agent2, is {current_turn}"
    
    print("\n✅ Verification Successful!")
    if os.path.exists("test_state_user.json"):
        os.remove("test_state_user.json")

if __name__ == "__main__":
    test_user_flow()
