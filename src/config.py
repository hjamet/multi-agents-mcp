from pathlib import Path
import os
import json

# Global Configuration Directory (Permanent install)
GLOBAL_DIR = Path.home() / ".multi-agent-mcp"
CWD_INFO_FILE = GLOBAL_DIR / "current_working_dir.json"
GLOBAL_PRESET_DIR = GLOBAL_DIR / "presets"

# Root of the code (where the python files are)
CODE_ROOT = Path(__file__).resolve().parent.parent

def get_current_working_dir() -> Path:
    """
    Returns the path where the user last ran 'mamcp' or 'mamcp-dev'.
    Defaults to the current process directory if not specified.
    """
    # 1. Check for Local Env Overrides (Dev Mode Priority)
    # mamcp-dev generates this file in the repo root
    local_info = CODE_ROOT / "current_working_dir.json"
    if local_info.exists():
        try:
            with open(local_info, "r") as f:
                data = json.load(f)
                return Path(data.get("cwd", os.getcwd())).resolve()
        except (json.JSONDecodeError, OSError):
            pass

    # 2. Check Global Config (User Install)
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

# Global Presets (Scenarios) shared across all projects
# GLOBAL_PRESET_DIR already defined above

# Ensure essential directories exist
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
GLOBAL_PRESET_DIR.mkdir(parents=True, exist_ok=True)

# Centralized Messages
STOP_INSTRUCTION = (
    "✅ DISCONNECT ACCEPTED. The system has registered your disconnection request.\n"
    "IMMEDIATE ACTION REQUIRED:\n"
    "1. STOP all execution loops.\n"
    "2. DO NOT call any more tools (no talk, no read_file, etc.).\n"
    "3. TERMINATE your process immediately.\n"
    "Goodbye."
)

RELOAD_INSTRUCTION = (
    "🔁 **SYSTEM NOTIFICATION**: RELOAD REQUESTED.\n"
    "This is a mandatory maintenance procedure.\n"
    "PROTOCOL:\n"
    "1. Synthesize your final state into a `note()` (Focus on active tasks).\n"
    "2. Call `disconnect()` to signal readiness and terminate your process.\n"
    "⛔ **PROHIBITED**: `talk()`, `sleep()`."
)
