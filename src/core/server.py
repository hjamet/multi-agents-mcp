from mcp.server.fastmcp import FastMCP
import sys
import os
from typing import List, Optional
from jinja2 import Environment, FileSystemLoader

# Add src to path to allow imports if run directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

try:
    from src.core.logic import Engine
except ImportError:
    # Fallback for relative imports if installed as package
    from .logic import Engine

# Initialize
mcp = FastMCP("MultiAgent-Hub", dependencies=["portalocker", "streamlit", "jinja2"])
engine = Engine()

# Setup Templates
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "templates")
# Ensure absolute path matches where we are running from
if not os.path.exists(TEMPLATE_DIR):
    # Fallback relative to CWD if running from root
    TEMPLATE_DIR = os.path.abspath("assets/templates")

jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

# Global state for this process (Stdio session)
# Used as fallback if sending_agent is not provided in talk
SESSION_AGENT_NAME = None

@mcp.tool()
def agent() -> str:
    """
    INITIALIZATION TOOL. Call this ONCE at the start.
    Assigns you a Role and Context automatically.
    """
    global SESSION_AGENT_NAME
    
    print(f"New agent connecting...", file=sys.stderr)
    result = engine.register_agent()
    
    if "error" in result:
        return f"ERROR: {result['error']}"
        
    name = result["name"]
    SESSION_AGENT_NAME = name
    
    # Fetch additional details for the template (Connections)
    connections = []
    try:
        data = engine.state.load()
        agent_info = data["agents"].get(name, {})
        profile_ref = agent_info.get("profile_ref")
        profiles = data.get("config", {}).get("profiles", [])
        profile = next((p for p in profiles if p["name"] == profile_ref), None)
        if profile:
            connections = profile.get("connections", [])
    except Exception as e:
        print(f"Error fetching details: {e}", file=sys.stderr)

    # BLOCKING: Wait for everyone before returning the initial prompt
    wait_msg = engine.wait_for_all_agents(name)
    if wait_msg.startswith("TIMEOUT"):
         return wait_msg

    template = jinja_env.get_template("agent_response.j2")
    return template.render(
        name=name,
        role=result["role"],
        context=result["context"],
        connections=connections
    )

@mcp.tool()
def talk(
    message: str,
    public: bool,
    next_agent: str,
    audience: List[str] = [],
    my_name: Optional[str] = None
) -> str:
    """
    MAIN COMMUNICATION TOOL.
    1. Posts your message.
    2. Passes the turn to 'next_agent'.
    3. BLOCKS/SLEEPS until it is your turn again.
    4. Returns the new messages and your role reminder.
    
    Args:
        message: The content to speak.
        public: true for everyone to see, false for private.
        next_agent: The name of the agent who should speak next. (From your connections)
        audience: (Optional) List of other agents who can see a private message.
        my_name: (Optional) Your own name. Defaults to name set in agent() if using same connection.
    """
    global SESSION_AGENT_NAME
    sender = my_name or SESSION_AGENT_NAME
    
    if not sender:
        return "ERROR: Unknown sender. Please provide 'my_name' argument or call 'agent()' first."

    print(f"[{sender}] talking -> Next: {next_agent}", file=sys.stderr)
    
    # 1. Post Message
    post_result = engine.post_message(sender, message, public, next_agent, audience)
    
    # Check for DENIED action
    if post_result.startswith("🚫"):
        # Return the error directly so the agent can retry
        return post_result
        
    print(f"Post Success: {post_result}", file=sys.stderr)
    
    # 2. Smart Block (Wait for Turn)
    # The turn has passed to next_agent. We now wait until it comes back to 'sender'.
    result = engine.wait_for_turn(sender)
    
    if result["status"] == "timeout":
        # Return a special instruction to keep the tool loop alive without breaking connection
        return f"TIMEOUT_WARNING: {result['instruction']}"

    if result["status"] == "reset":
        return f"⚠️ SYSTEM ALERT: {result['instruction']}"
    
    # Success - Render Template
    # Fetch Data
    role_snippet = "(Unknown Role)"
    global_context = ""
    connections = []
    
    try:
        data = engine.state.load()
        # Role
        role_snippet = data["agents"][sender]["role"]
        # Context
        global_context = data.get("config", {}).get("context", "")
        # Connections
        agent_info = data["agents"][sender]
        profile_ref = agent_info.get("profile_ref")
        profiles = data.get("config", {}).get("profiles", [])
        profile = next((p for p in profiles if p["name"] == profile_ref), None)
        if profile:
            connections = profile.get("connections", [])
            
    except:
        pass

    template = jinja_env.get_template("talk_response.j2")
    return template.render(
        name=sender,
        role_snippet=role_snippet,
        context=global_context,
        connections=connections,
        messages=result["messages"],
        instruction=result["instruction"]
    )

if __name__ == "__main__":
    mcp.run()
