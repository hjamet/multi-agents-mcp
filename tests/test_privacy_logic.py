
import sys
from unittest.mock import MagicMock
sys.modules["portalocker"] = MagicMock()

import pytest
from src.core.logic import Engine

# Mock State
@pytest.fixture
def mock_state():
    return {
        "agents": {
            "Alice": {
                "profile_ref": "Scientist", 
                "status": "connected",
                "connections": [{"target": "Miller", "authorized": True, "context": "Report"}]
            },
            "Bob": {
                "profile_ref": "Scientist", 
                "status": "connected"
            },
            "Charlie": {"profile_ref": "Engineer", "status": "connected"},
            "Miller": {"profile_ref": "Miller", "status": "connected"}
        },
        "messages": [],
        "config": {
            "profiles": [
                {"name": "Scientist", "capabilities": ["public", "private"]},
                {"name": "Engineer", "capabilities": ["public", "private"]},
                {"name": "Miller", "capabilities": ["public", "private"]}
            ]
        },
        "turn": {"current": "Alice"}
    }

class MockStateStore:
    def __init__(self, state):
        self.state = state
    def load(self):
        return self.state
    def update(self, func):
        return func(self.state)

def test_visibility_public_message(mock_state):
    store = MockStateStore(mock_state)
    engine = Engine(store)
    
    # Alice sends Public message mentioning Miller
    engine.post_message("Alice", "Hello World @Miller", True)
    
    print(f"DEBUG: Messages: {mock_state['messages']}")
    print(f"DEBUG: Turn: {mock_state['turn']}")

    # Verify Visibility
    # Miller should see it (Turn should be Miller)
    msgs_miller = engine.wait_for_turn("Miller")["messages"]
    assert len(msgs_miller) == 1
    assert msgs_miller[0]["content"] == "Hello World @Miller"
    
    # Charlie should see it IF IT IS HIS TURN
    mock_state["turn"]["current"] = "Charlie"
    msgs_charlie = engine.wait_for_turn("Charlie")["messages"]
    assert len(msgs_charlie) == 1

def test_visibility_private_message_direct(mock_state):
    store = MockStateStore(mock_state)
    engine = Engine(store)
    
    # Alice sends Private message to Miller
    engine.post_message("Alice", "Secret for Miller @Miller", False)
    
    # 1. Miller (Target) should see it
    msgs_miller = engine.wait_for_turn("Miller")["messages"]
    assert len(msgs_miller) == 1
    assert msgs_miller[0]["content"] == "Secret for Miller @Miller"
    
    # 2. Alice (Sender) should see it (Force turn)
    mock_state["turn"]["current"] = "Alice"
    msgs_alice = engine.wait_for_turn("Alice")["messages"]
    assert len(msgs_alice) == 1
    
    # 3. Charlie (Outsider, diff role) should NOT see it (Force turn)
    mock_state["turn"]["current"] = "Charlie"
    msgs_charlie = engine.wait_for_turn("Charlie")["messages"]
    assert len(msgs_charlie) == 0

def test_visibility_private_message_team(mock_state):
    store = MockStateStore(mock_state)
    engine = Engine(store)
    
    # Alice (Scientist) sends Private message to Miller
    engine.post_message("Alice", "Team Secret @Miller", False)
    
    # Miller Turn by default
    
    # Bob (Scientist, Same Role as Alice) should NOT see it (Strict Privacy)
    mock_state["turn"]["current"] = "Bob"
    msgs_bob = engine.wait_for_turn("Bob")["messages"]
    assert len(msgs_bob) == 0
    
    # Charlie (Engineer, Diff Role) should NOT see it
    mock_state["turn"]["current"] = "Charlie"
    msgs_charlie = engine.wait_for_turn("Charlie")["messages"]
    assert len(msgs_charlie) == 0

def test_visibility_private_message_audience(mock_state):
    store = MockStateStore(mock_state)
    engine = Engine(store)
    
    # Alice sends Private message to Miller, mentioning Charlie in audience
    # Charlie is an Engineer (Diff role from Alice)
    engine.post_message("Alice", "Secret with Charlie @Miller", False, audience=["Charlie"])
    
    # 1. Miller (Target) should see it
    msgs_miller = engine.wait_for_turn("Miller")["messages"]
    assert len(msgs_miller) == 1
    
    # 2. Charlie (Audience) should see it
    mock_state["turn"]["current"] = "Charlie"
    msgs_charlie = engine.wait_for_turn("Charlie")["messages"]
    assert len(msgs_charlie) == 1
    assert msgs_charlie[0]["content"] == "Secret with Charlie @Miller"
    
    # 3. Bob (Scientist, same role as Alice) should NOT see it (Strict Privacy)
    mock_state["turn"]["current"] = "Bob"
    msgs_bob = engine.wait_for_turn("Bob")["messages"]
    assert len(msgs_bob) == 0
