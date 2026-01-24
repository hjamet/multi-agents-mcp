
import sys
from unittest.mock import MagicMock
sys.modules["portalocker"] = MagicMock()

import pytest
import time
from src.core.logic import Engine
from src.core.models import TurnQueueItem

class MockStateStore:
    def __init__(self):
        self.data = {
            "agents": {
                "Agent1": {"status": "connected", "profile_ref": "P1"},
                "Agent2": {"status": "connected", "profile_ref": "P2"},
                "Agent3": {"status": "connected", "profile_ref": "P3"},
                "Agent4": {"status": "connected", "profile_ref": "P4"},
            },
            "config": {
                "profiles": [
                    {"name": "P1", "capabilities": ["public"], "connections": [{"target": "Agent2", "authorized": True}, {"target": "Agent3", "authorized": True}, {"target": "Agent4", "authorized": True}]},
                    {"name": "P2", "capabilities": ["public"], "connections": [{"target": "Agent1", "authorized": True}, {"target": "Agent3", "authorized": True}]},
                    {"name": "P3", "capabilities": ["public"], "connections": [{"target": "Agent1", "authorized": True}]},
                    {"name": "P4", "capabilities": ["public"], "connections": [{"target": "Agent1", "authorized": True}]}
                ]
            },
            "turn": {"current": "Agent1", "queue": []},
            "messages": []
        }
    
    def load(self):
        return self.data
    
    def update(self, callback):
        result = callback(self.data)
        # In real StateStore, update returns the result of the callback.
        # But wait, logic.py: post_message returns self.state.update(_post).
        # And _post returns the message string.
        # So update MUST return what callback returns.
        return result

@pytest.fixture
def engine():
    e = Engine(MockStateStore())
    return e

def test_queue_ordering(engine):
    # Agent1 mentions Agent2 (@Agent2) then Agent3 (@Agent3)
    # Queue should be [Agent2(1), Agent3(1)] (Timestamp order)
    
    engine.post_message("Agent1", "Hello @Agent2 and @Agent3", True)
    
    state = engine.state.load()
    print(f"DEBUG STATE: Turn Current: {state['turn']['current']}, Queue: {state['turn']['queue']}")
    assert state["turn"]["current"] == "Agent2"
    queue = state["turn"]["queue"]
    assert len(queue) == 1
    assert queue[0]["name"] == "Agent3"
    assert queue[0]["count"] == 1
    
    # Now Agent2 speaks and mentions Agent1 and Agent3
    # Queue was [Agent3(1)], New mentions: Agent1, Agent3
    # Agent3 count becomes 2. Agent1 count becomes 1.
    # Order: Count DESC -> Agent3(2), Agent1(1).
    
    engine.post_message("Agent2", "Hi @Agent1 and @Agent3 again", True)
    
    state = engine.state.load()
    assert state["turn"]["current"] == "Agent3" # Top of queue
    queue = state["turn"]["queue"]
    # Queue should have Agent1 left. Agent3 was popped.
    # Wait, let's trace:
    # Queue before: [Agent3(1)]
    # Mentions: Agent1, Agent3
    # Update: Agent3 count -> 2, Agent1 added(1).
    # Queue: [Agent3(2), Agent1(1)] (Sorted by Count DESC)
    # Transition: Pop Agent3. Agent3 count -> 1. 
    # Logic: if count > 0, keep in queue? Check implementation.
    # Ah, implementation: "next_item.count -= 1. if next_item.count <= 0: queue.pop(0)"
    # So Agent3(2) becomes Agent3(1) and STAYS in queue?
    # NO. We pop(0) ONLY if count <= 0.
    # IMPLEMENTATION CHECK:
    # next_item = queue[0] (Agent3)
    # next_item.count -= 1 (becomes 1)
    # if next_item.count <= 0: queue.pop(0) -> False.
    # So Agent3 stays at head? 
    # Wait, if Agent3 speaks NEXT, does it consume its own turn?
    # No, effectively Agent3 is the NEXT speaker.
    # But he is still in the queue for his *second* turn?
    # The requirement: "si un agent mentionne ... @agent1, @agent2 ... les 3 prochaines personnes ... @agent1, @agent2".
    # This implies standard FIFO if counts are 1.
    # With priorities: "@agent2 (2 voies), @agent3 (1 voie)".
    # Means Agent2 speaks, then Agent2 speaks AGAIN? Or just priority?
    # "on doit avoir un système de voies qui permet de mettre à jour la fil d'attente pour savoir quel sera le prochain agent à parler"
    # Usually multi-turn means they speak, preserving order.
    
    assert len(queue) == 1
    assert queue[0]["name"] == "Agent1"
    
    # Next turn: Agent3 speaks.
    # In the current implementation, an agent MUST mention someone.
    resp = engine.post_message("Agent3", "I am speaking.", True)
    assert "🚫 TURN ERROR" in resp
    
    # So the test must be updated to include a mention to proceed
    engine.post_message("Agent3", "I am speaking to @Agent1", True)
    
    state = engine.state.load()
    assert state["turn"]["current"] == "Agent1" # Agent1 is next
    
    # Agent1 speaks and passes to User explicitly
    engine.post_message("Agent1", "Fin. @User", True)
    state = engine.state.load()
    assert state["turn"]["current"] == "User" # Default when empty

def test_permission_error(engine):
    # Agent2 only authorized to talk to Agent1.
    # Try mentioning Agent4 (fail)
    
    # Hijack turn to Agent2
    engine.state.data["turn"]["current"] = "Agent2"
    
    resp = engine.post_message("Agent2", "Hey @Agent4", True)
    assert "🚫 PERMISSION ERROR" in resp

def test_empty_queue_error(engine):
    engine.state.data["turn"]["current"] = "Agent1"
    resp = engine.post_message("Agent1", "No mentions here", True)
    assert "🚫 TURN ERROR" in resp
