import sys
import os

print(f"CWD: {os.getcwd()}")
print(f"Path: {sys.path}")

try:
    from src.config import PROJECT_ROOT, TEMPLATE_DIR, MEMORY_DIR, STATE_FILE
    print("✅ src.config imported successfully")
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"TEMPLATE_DIR: {TEMPLATE_DIR}")
    print(f"MEMORY_DIR: {MEMORY_DIR}")
    print(f"STATE_FILE: {STATE_FILE}")
except Exception as e:
    print(f"❌ Failed to import src.config: {e}")

try:
    from src.core.state import StateStore
    print("✅ src.core.state imported successfully")
except Exception as e:
    print(f"❌ Failed to import src.core.state: {e}")

try:
    from src.core.server import mcp
    print("✅ src.core.server imported successfully")
except Exception as e:
    print(f"❌ Failed to import src.core.server: {e}")
