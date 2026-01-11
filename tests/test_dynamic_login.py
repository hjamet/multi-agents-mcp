import unittest
import uuid
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.core.logic import Engine
from src.core.state import StateStore

class TestDynamicLogin(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_login_{uuid.uuid4()}.json"
        self.store = StateStore(file_path=self.db_path)
        self.engine = Engine(state_store=self.store)
        self.store._initialize_if_missing()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_anonymous_assignment(self):
        """
        Test that register_agent() (no args) assigns pending roles correctly.
        """
        # 1. Setup Pending Agents (like Werewolf setup)
        def setup(s):
            s["agents"] = {
                "Wolf_1": {"role": "You are a wolf", "status": "pending_connection"},
                "Villager_1": {"role": "You are a villager", "status": "pending_connection"},
                "Taken_1": {"role": "Taken", "status": "connected"}
            }
            return "Setup"
        self.store.update(setup)
        
        # 2. First Claim
        res1 = self.engine.register_agent()
        self.assertNotIn("error", res1)
        name1 = res1["name"]
        print(f"Claimed 1: {name1}")
        
        # 3. Second Claim
        res2 = self.engine.register_agent()
        self.assertNotIn("error", res2)
        name2 = res2["name"]
        print(f"Claimed 2: {name2}")
        
        self.assertNotEqual(name1, name2)
        
        # 4. Third Claim (Should fail, only 2 pending were avail)
        res3 = self.engine.register_agent()
        self.assertIn("error", res3)
        print(f"Claimed 3: {res3}")

if __name__ == "__main__":
    unittest.main()
