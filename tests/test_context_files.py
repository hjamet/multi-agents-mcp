import pytest
import os
import json
import time
import sys
# Add current directory to sys.path to allow relative imports if needed
sys.path.append(os.path.dirname(__file__))
from test_orchestration import ServerProcess, server_single

def test_context_files_generation(server_single):
    """
    Verifies that MEMORY.md and CONVERSATION.md are created in the server's working directory
    when agent and talk tools are called.
    """
    proc = server_single
    
    # 1. Register Agent
    # This triggers 'agent' tool which should create the files (empty or initial)
    resp = proc.call_tool("agent", {})
    assert "REGISTRATION SUCCESSFUL" in resp
    
    # Check if files exist
    # The server is running in the same directory as the test (for now, or CWD)
    # verify_logic.py sets CWD to the project root or similar. 
    # Helper: server.py uses EXECUTION_DIR which is get_current_working_dir().
    # In test_orchestration, we run python server.py. usage CWD is inherited.
    # We need to know where the server thinks is CWD.
    
    # Let's assume CWD is where we ran pytest from, which is likely project root.
    cwd = os.getcwd()
    memory_file = os.path.join(cwd, "MEMORY.md")
    conversation_file = os.path.join(cwd, "CONVERSATION.md")
    
    # Wait briefly for file system
    time.sleep(0.5)
    
    assert os.path.exists(memory_file), f"MEMORY.md not found in {cwd}"
    assert os.path.exists(conversation_file), f"CONVERSATION.md not found in {cwd}"
    
    # 2. Add a Note (Update Memory)
    note_content = "This is a test note for context file verification."
    proc.call_tool("note", {"content": note_content, "from_agent": "Agent1"})
    
    # 3. Talk (Trigger Context Update)
    # The 'talk' tool re-generates the context files before returning the prompt
    msg_content = "Hello, checking context files."
    proc.call_tool("talk", {
        "message": msg_content, 
        "public": True, 
        "to": "User", 
        "from_agent": "Agent1"
    })
    
    # Verify Content of MEMORY.md
    with open(memory_file, "r") as f:
        mem_content = f.read()
    assert note_content in mem_content
    
    # Verify Content of CONVERSATION.md
    with open(conversation_file, "r") as f:
        conv_content = f.read()
    assert msg_content in conv_content
    assert "Agent1" in conv_content
    
    print("✅ Context files verification passed.")

    # Cleanup
    if os.path.exists(memory_file):
        os.remove(memory_file)
    if os.path.exists(conversation_file):
        os.remove(conversation_file)
