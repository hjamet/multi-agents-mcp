import sys
import os
from src.utils.logger import get_logger

logger = get_logger()
logger.log("INFO", "Test", "Starting system checks...")

try:
    from src.config import PROJECT_ROOT
    print(f"✅ Config OK: {PROJECT_ROOT}")
except ImportError as e:
    print(f"❌ Config Fail: {e}")

try:
    from src.core.models import GlobalState
    print(f"✅ Models OK")
except ImportError as e:
    print(f"❌ Models Fail: {e}")

try:
    from src.core.state import StateStore
    store = StateStore()
    data = store.load()
    print(f"✅ State Load OK. Keys: {list(data.keys())}")
except Exception as e:
    print(f"❌ State Load Fail: {e}")

print("✅ Checks Complete")
