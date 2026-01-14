import sys
from pathlib import Path
sys.path.insert(0, "/home/lopilo/code/multi-agents-mcp")
from src.core.state import StateStore

store = StateStore()

def fix(state):
    current = state.get("turn", {}).get("current")
    if current == "Alex":
        # Find the real Alex
        for aid, data in state.get("agents", {}).items():
            if data.get("profile_ref") == "Alex":
                state["turn"]["current"] = aid
                return f"Fixed: Alex -> {aid}"
    return f"No fix needed (Current: {current})"

try:
    print(store.update(fix))
except Exception as e:
    print(f"Error: {e}")
