import streamlit as st
import importlib.util
import sys
import os
from pathlib import Path

# --- DYNAMIC LOADER ---
def load_and_run(file_path):
    try:
        spec = importlib.util.spec_from_file_location("dynamic_module", file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["dynamic_module"] = module
        spec.loader.exec_module(module)
        if hasattr(module, "main"):
            module.main()
        else:
            st.warning(f"File {file_path.name} has no `main()` function.")
    except Exception as e:
        st.error(f"Error loading {file_path.name}: {e}")

def main():
    # st.title("📊 Agents Result Explorer") # Removed effectively (Double Header)
    
    # 1. Scan for subpages
    current_dir = Path(__file__).parent
    subpages_dir = current_dir / "subpages"
    
    if not subpages_dir.exists():
        st.error(f"Directory not found: {subpages_dir}")
        return

    files = sorted([f for f in subpages_dir.iterdir() if f.name.endswith(".py")])
    
    if not files:
        st.info("No pages found in `mamcp-streamlit/subpages/`.")
        return
        
    # 2. Sidebar Navigation
    page_names = [f.name for f in files]
    
    # Use query param or session state to persist selection?
    # Simple sidebar selectbox is enough for now.
    selected_page_name = st.sidebar.radio("📚 Result Pages", page_names, key="dashboard_page_selection")
    
    # 3. Load Selected Pgae
    if selected_page_name:
        selected_file = next((f for f in files if f.name == selected_page_name), None)
        if selected_file:
            st.markdown("---")
            load_and_run(selected_file)

if __name__ == "__main__":
    main()
