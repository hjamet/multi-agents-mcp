from pathlib import Path
import os

# Base Paths
# This file is in src/config.py
# PROJECT_ROOT is 2 levels up if config is in src/
# Wait, src/config.py -> parent is src -> parent is root. So 2 levels.
# But previously I said 3 levels: config.py (src) -> src (parent) -> root (parent of src)?
# File: /path/to/project/src/config.py
# .parent -> /path/to/project/src
# .parent.parent -> /path/to/project
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Assets
ASSETS_DIR = PROJECT_ROOT / "assets"
TEMPLATE_DIR = ASSETS_DIR / "templates"
MEMORY_DIR = ASSETS_DIR / "memory"
LOGS_DIR = PROJECT_ROOT / "logs"

# Ensure directories exist
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# State
STATE_FILE = PROJECT_ROOT / "state.json"
