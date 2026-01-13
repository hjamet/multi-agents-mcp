from pathlib import Path
import os
import json

# Global Configuration Directory (Permanent install)
GLOBAL_DIR = Path.home() / ".multi-agent-mcp"
CWD_INFO_FILE = GLOBAL_DIR / "current_working_dir.json"

# Root of the code (where the python files are)
CODE_ROOT = Path(__file__).resolve().parent.parent

def get_current_working_dir() -> Path:
    """
    Returns the path where the user last ran 'mamcp'.
    Defaults to the current process directory if not specified.
    """
    if CWD_INFO_FILE.exists():
        try:
            with open(CWD_INFO_FILE, "r") as f:
                data = json.load(f)
                return Path(data.get("cwd", os.getcwd())).resolve()
        except (json.JSONDecodeError, OSError):
            pass
    return Path(os.getcwd()).resolve()

# Project-Specific Data Directory (Local to the execution path)
EXECUTION_DIR = get_current_working_dir()
LOCAL_DATA_DIR = EXECUTION_DIR / ".multi-agent-mcp"

# Assets (Always bundled with the code)
ASSETS_DIR = CODE_ROOT / "assets"
TEMPLATE_DIR = ASSETS_DIR / "templates"

# Project-Specific Assets (State and Memory)
# They are stored in the local .multi-agent-mcp folder
STATE_FILE = LOCAL_DATA_DIR / "state.json"
MEMORY_DIR = LOCAL_DATA_DIR / "memory"
LOGS_DIR = LOCAL_DATA_DIR / "logs"

# Ensure essential directories exist
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
