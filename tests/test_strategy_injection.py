import unittest
import time
import uuid
import os
import sys
import shutil

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.core.logic import Engine
from src.core.state import StateStore

class TestStrategyInjection(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_strategy_{uuid.uuid4()}.json"
        self.store = StateStore(file_path=self.db_path)
        self.engine = Engine(state_store=self.store)
        
        self.store._initialize_if_missing()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_strategy_advice(self):
        """
        Test that wait_for_turn injects advice from profile connections.
        """
        # 1. Setup State with Profile and Connections
        def setup_state(s):
            s["config"]["profiles"] = [
                {
                    "name": "Wolf", 
                    "connections": [
                        {"target": "Villager", "context": "Eat them."}
                    ]
                }
            ]
            s["agents"]["Wolf_1"] = {
                "role": "You are a wolf", 
                "status": "connected",
                "profile_ref": "Wolf"
            }
            s["turn"]["current"] = "Wolf_1"
            return "Setup done"
            
        self.store.update(setup_state)
        
        # 2. Call wait_for_turn
        # Since it's already my turn, it should return success immediately
        result = self.engine.wait_for_turn("Wolf_1", timeout_seconds=2)
        
        # 3. Verify
        print(f"\nCaught Instruction: {result['instruction']}")
        
        self.assertEqual(result["status"], "success")
        self.assertIn("--- STRATEGIC ADVICE ---", result["instruction"])
        self.assertIn("If talking to Villager: Eat them.", result["instruction"])
        print("✅ Strategy Advice Injected Successfully!")

if __name__ == "__main__":
    unittest.main()
