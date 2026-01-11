import json
import os
import portalocker
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# Resolve absolute path to state.json to ensure all processes (Streamlit, MCP Server)
# view the same file regardless of their Current Working Directory.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STATE_FILE = os.path.join(PROJECT_ROOT, "state.json")

@dataclass
class StateStore:
    """
    Manages access to the shared state.json file with locking.
    """
    file_path: str = STATE_FILE
    
    def _initialize_if_missing(self):
        if not os.path.exists(self.file_path):
            initial_state = {
                "messages": [],
                "conversation_id": str(uuid.uuid4()), # Track conversation life-cycle for resets
                "turn": {"current": None, "next": None},
                "agents": {}, # agent_name -> {role: str, status: str}
                "config": {"total_agents": 2} # Default, can be overridden
            }
            with open(self.file_path, "w") as f:
                json.dump(initial_state, f, indent=2)

    def load(self) -> Dict[str, Any]:
        """
        Reads the state from the file with a shared lock (implicit in some systems, 
        but here we usually just read given we will likely write right after).
        For simplicity and safety in this turn-based system, we'll use an exclusive lock 
        even for reading if we plan to modify, but here we separate concerns.
        
        To avoid complex lock upgrades, we will rely on usage patterns:
        - simple read (no lock needed if acceptable race condition, but better use lock)
        - atomic update (lock, read, write, unlock)
        """
        self._initialize_if_missing()
        # For atomic operations, logic.py will usually handle the locking flow.
        # But providing a raw read method:
        try:
            with portalocker.Lock(self.file_path, 'r', timeout=10) as f:
                return json.load(f)
        except Exception as e:
            # Fallback or error handling
            print(f"Error reading state: {e}")
            return {}

    def update(self, callback) -> Any:
        """
        Atomically updates the state.
        'callback' is a function that takes the current state (dict) and returns a value.
        The state object passed to callback is mutable; modifications are saved.
        """
        self._initialize_if_missing()
        
        # Open with EXCLUSIVE lock
        with portalocker.Lock(self.file_path, 'r+', timeout=60) as f:
            content = f.read()
            if not content:
                state = {}
            else:
                state = json.loads(content)
            
            # Apply transformation
            result = callback(state)
            
            # Write back
            f.seek(0)
            f.truncate()
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno()) # Ensure write to disk
            
            return result
