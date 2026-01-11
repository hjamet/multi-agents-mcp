import unittest
import time
import uuid
import os
import sys
from threading import Thread

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.core.logic import Engine
from src.core.state import StateStore

class TestResetFlow(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_reset_{uuid.uuid4()}.json"
        self.store = StateStore(file_path=self.db_path)
        self.engine = Engine(state_store=self.store)
        
        # Initialize
        self.store._initialize_if_missing()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_reset_signal(self):
        """
        Test that an agent waiting for turn receives 'reset' status when conversation_id changes.
        """
        agent_name = "Agent1"
        
        # 1. Start waiting in a thread (simulate agent)
        result_container = {}
        
        def wait_task():
            # This should block until timeout or reset
            res = self.engine.wait_for_turn(agent_name, timeout_seconds=5)
            result_container["result"] = res
            
        t = Thread(target=wait_task)
        t.start()
        
        # 2. Sleep briefly to let it enter the loop
        time.sleep(1)
        
        # 3. Trigger Reset (Change conversation_id in state)
        def trigger_reset(state):
            state["conversation_id"] = str(uuid.uuid4())
            return "Reset done"
            
        self.store.update(trigger_reset)
        
        # 4. Wait for thread
        t.join()
        
        # 5. Verify
        result = result_container.get("result")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "reset")
        self.assertIn("SYSTEM RESET", result["instruction"])
        print("\n✅ Agent successfully detected RESET signal!")

if __name__ == "__main__":
    unittest.main()
