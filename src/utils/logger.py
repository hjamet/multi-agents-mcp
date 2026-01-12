import json
import time
import sys
import os
from threading import Lock

class GameLogger:
    _instance = None
    _lock = Lock()
    
    def __new__(cls, log_file="game_transcript.jsonl"):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(GameLogger, cls).__new__(cls)
                cls._instance._init(log_file)
            return cls._instance

    def _init(self, log_file):
        # Determine log path: relative to CWD if possible
        # Default to a 'logs' directory
        self.log_dir = "logs"
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)
            
        self.log_path = os.path.join(self.log_dir, log_file)
        self.file_lock = Lock()

    def reset(self):
        """Clear the log file content."""
        with self.file_lock:
            with open(self.log_path, "w", encoding="utf-8") as f:
                f.write("") # Truncate

    def log(self, event_type: str, agent: str, content: str, metadata: dict = None):
        """
        Log an event to the JSONL file.
        """
        entry = {
            "timestamp": time.time(),
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "type": event_type,
            "agent": agent,
            "content": content,
            "metadata": metadata or {}
        }
        
        json_line = json.dumps(entry, ensure_ascii=False)
        
        # File Output
        with self.file_lock:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json_line + "\n")
                
        # Console Output (stderr for MCP visibility)
        try:
            # Format: [TYPE] Agent: Content
            short_content = content[:100] + "..." if len(content) > 100 else content
            print(f"[{event_type}] {agent}: {short_content}", file=sys.stderr)
        except:
            pass

    def error(self, agent: str, error_msg: str, context: str = ""):
        self.log("ERROR", agent, error_msg, {"context": context})

# Global instance accessor
_logger = None
def get_logger():
    global _logger
    if _logger is None:
        _logger = GameLogger()
    return _logger
