import unittest
import time
import uuid
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.core.logic import Engine
from src.core.state import StateStore

class TestEnforcement(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_enforce_{uuid.uuid4()}.json"
        self.store = StateStore(file_path=self.db_path)
        self.engine = Engine(state_store=self.store)
        self.store._initialize_if_missing()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _setup_agent(self, name, caps, connections=[]):
        def update(s):
            s.setdefault("config", {}).setdefault("profiles", [])
            # Create Profile
            profile = {
                "name": name,
                "capabilities": caps,
                "connections": connections,
                "count": 1
            }
            s["config"]["profiles"].append(profile)
            
            # Create Agent Instance
            s.setdefault("agents", {})[f"{name}_1"] = {
                "role": "Role",
                "status": "connected",
                "profile_ref": name
            }
            # Also create a dummy target "Villager"
            if not any(p["name"] == "Villager" for p in s["config"]["profiles"]):
                 s["config"]["profiles"].append({"name": "Villager", "count": 1})
                 s["agents"]["Villager_1"] = {"profile_ref": "Villager"}

            return "Agent Created"
        self.store.update(update)

    def test_public_denial(self):
        self._setup_agent("ShyGuy", ["private"]) # No public
        res = self.engine.post_message("ShyGuy_1", "Hello", public=True, next_agent="Villager_1", audience=[])
        self.assertIn("🚫 ACTION DENIED", res)
        self.assertIn("'public' capability", res)

    def test_private_denial(self):
        self._setup_agent("LoudMouth", ["public"]) # No private
        res = self.engine.post_message("LoudMouth_1", "Psst", public=False, next_agent="Villager_1", audience=[])
        self.assertIn("🚫 ACTION DENIED", res)
        self.assertIn("'private' capability", res)

    def test_connection_denial(self):
        # Can private, but no connection to Villager
        self._setup_agent("Stranger", ["private"], connections=[]) 
        res = self.engine.post_message("Stranger_1", "Hi", public=False, next_agent="Villager_1", audience=[])
        self.assertIn("🚫 ACTION DENIED", res)
        self.assertIn("not authorized to speak to 'Villager_1'", res)

    def test_connection_success(self):
        # Connected to Villager
        self._setup_agent("Friend", ["private"], connections=[{"target": "Villager", "context": "Hi"}])
        res = self.engine.post_message("Friend_1", "Hi", public=False, next_agent="Villager_1", audience=[])
        self.assertNotIn("🚫", res)
        self.assertIn("Message posted", res)

    def test_open_mode(self):
        # Open mode, no connections defined
        self._setup_agent("God", ["open", "private"], connections=[])
        res = self.engine.post_message("God_1", "I see all", public=False, next_agent="Villager_1", audience=[])
        self.assertNotIn("🚫", res)
        self.assertIn("Message posted", res)

if __name__ == "__main__":
    unittest.main()
