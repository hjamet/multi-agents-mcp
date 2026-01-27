import streamlit as st

def main():
    st.header("📈 Example Analysis")
    st.info("This is an example subpage. You can delete it.")
    st.write("Agents should create new files in `mamcp-streamlit/subpages/` to add new tabs here.")
    st.line_chart([10, 20, 15, 25, 30])

if __name__ == "__main__":
    main()
