import streamlit as st
from pathlib import Path
import datetime
import os

# Callback to update state BEFORE the widget renders next time
def nav_to(page_name):
    st.session_state["dashboard_page_selection"] = page_name

def delete_page(file_path):
    try:
        os.remove(file_path)
        # If currently selected page is the one deleted, we might need a reset, 
        # but dashboard.py handles missing selection gracefully usually.
        # Force a Toast
        st.toast(f"🗑️ Deleted {file_path.name}")
    except Exception as e:
        st.toast(f"❌ Error deleting: {e}")

def main():
    st.header("🏠 Dashboard Overview")
    st.write("Navigate to available pages (sorted by recent activity):")
    
    current_dir = Path(__file__).parent
    # Get all python files except self
    files = [f for f in current_dir.iterdir() if f.name.endswith(".py") and f.name != "00_Home.py"]
    
    # Sort by modification time (Newest First)
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not files:
        st.info("No pages found yet.")
        return

    # Create a clickable list using buttons
    for f in files:
        mod_time = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        
        # Display as a row: Date | Button | Delete
        col1, col2, col3 = st.columns([2, 6, 1])
        with col1:
            st.caption(f"📅 {mod_time}")
            
        with col2:
            # Full width nav button
            st.button(f"📄 {f.name}", 
                      key=f"nav_{f.name}", 
                      use_container_width=True, 
                      on_click=nav_to, 
                      args=(f.name,))
                      
        with col3:
            # Delete button
            st.button("🗑️", 
                      key=f"del_{f.name}", 
                      help="Delete page permanently",
                      on_click=delete_page, 
                      args=(f,))

if __name__ == "__main__":
    main()
