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
        # Check if pinned, remove if so
        if "pinned_pages" in st.session_state and file_path.name in st.session_state.pinned_pages:
            st.session_state.pinned_pages.remove(file_path.name)
        st.toast(f"🗑️ Deleted {file_path.name}")
    except Exception as e:
        st.toast(f"❌ Error deleting: {e}")

def toggle_pin(page_name):
    if "pinned_pages" not in st.session_state:
        st.session_state.pinned_pages = []
    
    if page_name in st.session_state.pinned_pages:
        st.session_state.pinned_pages.remove(page_name)
    else:
        st.session_state.pinned_pages.append(page_name)

def main():
    st.header("🏠 Dashboard Overview")
    st.write("Navigate to available pages.")
    
    # Initialize Pinned State
    if "pinned_pages" not in st.session_state:
        st.session_state.pinned_pages = []
    
    current_dir = Path(__file__).parent
    # Get all python files except self
    files = [f for f in current_dir.iterdir() if f.name.endswith(".py") and f.name != "00_Home.py"]
    
    if not files:
        st.info("No pages found yet.")
        return

    # Sort Logic: Pinned First, then Date
    pinned_files = []
    unpinned_files = []
    
    for f in files:
        if f.name in st.session_state.pinned_pages:
            pinned_files.append(f)
        else:
            unpinned_files.append(f)
            
    # Sort both lists by date (newest first)
    pinned_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    unpinned_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    sorted_files = pinned_files + unpinned_files

    # Create a clickable list using buttons
    for f in sorted_files:
        mod_time = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        is_pinned = f.name in st.session_state.pinned_pages
        
        # Display as a row: Date | Button | Pin | Delete
        col1, col2, col3, col4 = st.columns([2, 5, 1, 1])
        with col1:
            st.caption(f"📅 {mod_time}")
            
        with col2:
            # Highlight pinned items slightly?
            label = f"📍 {f.name}" if is_pinned else f"📄 {f.name}"
            st.button(label, 
                      key=f"nav_{f.name}", 
                      use_container_width=True, 
                      on_click=nav_to, 
                      args=(f.name,))
                      
        with col3:
            pin_icon = "🔓" if is_pinned else "📌"
            help_txt = "Unpin" if is_pinned else "Pin to top"
            st.button(pin_icon, 
                      key=f"pin_{f.name}", 
                      help=help_txt,
                      on_click=toggle_pin, 
                      args=(f.name,))
                      
        with col4:
            st.button("🗑️", 
                      key=f"del_{f.name}", 
                      help="Delete page permanently",
                      on_click=delete_page, 
                      args=(f,))

if __name__ == "__main__":
    main()
