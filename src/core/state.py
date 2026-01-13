import json
import os
import portalocker
import uuid
import time
import random
from src.utils.logger import get_logger
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# Resolve absolute path -> Now handled in src.config
from src.config import STATE_FILE

# Type alias or check if we need to convert to str
# Usually Path objects are fine in open(), but for safety/typing we use them directly

logger = get_logger()

from src.core.models import GlobalState
from pydantic import ValidationError

@dataclass
class StateStore:
    """
    Manages access to the shared state.json file with locking.
    """
    file_path: str = str(STATE_FILE) # Ensure str type for portalocker compatibility
    
    def __post_init__(self):
        # Allow override via env var for testing
        if os.environ.get("MULTI_AGENT_STATE_PATH"):
            self.file_path = os.environ["MULTI_AGENT_STATE_PATH"]

    def _initialize_if_missing(self):
        if not os.path.exists(self.file_path):
            initial_state = {
                "messages": [],
                "conversation_id": str(uuid.uuid4()),
                "turn": {"current": None, "next": None},
                "agents": {},
                "config": {"total_agents": 2}
            }
            # Use atomic write pattern with temp file if robust, but simple write is fine for init
            with open(self.file_path, "w") as f:
                json.dump(initial_state, f, indent=2)

    def load(self) -> Dict[str, Any]:
        """
        Reads with Shared Lock (Non-blocking preference).
        """
        self._initialize_if_missing()
        
        # Try-Loop for robustness
        for i in range(5): # Increased retries
            try:
                # Use LOCK_SH | LOCK_NB to ensure we fail fast and retry if locked
                flags = portalocker.LOCK_SH | portalocker.LOCK_NB
                with portalocker.Lock(self.file_path, 'r', flags=flags) as f:
                    content = f.read()
                    if not content: return {}
                    data = json.loads(content)
                    
                    # Validation
                    try:
                        GlobalState.model_validate(data)
                    except ValidationError as e:
                        logger.error("StateStore", f"State Validation Failed: {e}")
                    
                    return data
            except (portalocker.LockException, BlockingIOError, OSError):
                time.sleep(random.uniform(0.05, 0.2))
                continue
            except json.JSONDecodeError:
                return {}
        
        # Fallback: Just try reading without lock (dirty read)
        # This prevents UI hang if someone died holding lock
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except:
             return {}

    def update(self, callback) -> Any:
        """
        Atomically updates the state with Exclusive Lock.
        """
        self._initialize_if_missing()
        
        # Retry loop for acquiring write lock
        # Increased to 50 to handle high contention during startup bursts
        max_retries = 50 
        for i in range(max_retries):
            try:
                # LOCK_EX | LOCK_NB
                flags = portalocker.LOCK_EX | portalocker.LOCK_NB
                
                # 'r+' is needed to read then write.
                with portalocker.Lock(self.file_path, 'r+', flags=flags) as f:
                    f.seek(0)
                    content = f.read()
                    
                    if not content:
                         state = {}
                    else:
                        try:
                            state = json.loads(content)
                        except json.JSONDecodeError:
                            # Critical failure or empty file
                            state = {}
                    
                    # Apply transformation
                    result = callback(state)
                    
                    # Write back
                    f.seek(0)
                    f.truncate()
                    json.dump(state, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                    
                    return result
            except (portalocker.LockException, BlockingIOError):
                # Backoff
                sleep_time = random.uniform(0.1, 0.5)
                time.sleep(sleep_time)
                continue
            except Exception as e:
                logger.error("StateStore", f"Update Error: {e}")
                raise e
        
        raise Exception("Failed to acquire state lock after multiple retries.")
