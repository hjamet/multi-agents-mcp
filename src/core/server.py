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

def _get_agent_connections(state, agent_name):
    """
    Resolve connections for an agent.
    Priority: Instance 'connections' > Profile 'connections'
    """
    connections = []
    try:
        agent_info = state["agents"].get(agent_name, {})
        
        # 1. Check Instance Level
        if "connections" in agent_info:
            return agent_info["connections"]
            
        # 2. Check Profile Level
        profile_ref = agent_info.get("profile_ref")
        profiles = state.get("config", {}).get("profiles", [])
        profile = next((p for p in profiles if p["name"] == profile_ref), None)
        
        if profile:
            return profile.get("connections", [])
            
    except Exception as e:
        print(f"Error resolving connections for {agent_name}: {e}", file=sys.stderr)
        
    return connections

def _build_agent_directory(state, my_name):
    """
    Build a comprehensive list of all agents for the prompt.
    Includes public info and specific connection notes.
    """
    directory = []
    
    # My Info
    my_info = state["agents"].get(my_name, {})
    my_profile_ref = my_info.get("profile_ref")
    profiles = state.get("config", {}).get("profiles", [])
    my_profile = next((p for p in profiles if p["name"] == my_profile_ref), {})
    my_caps = my_profile.get("capabilities", [])
    is_open_mode = "open" in my_caps
    
    # My Connections (List of dicts {target, context})
    my_connections = _get_agent_connections(state, my_name)
    # Map target -> context
    conn_map = {c["target"]: c["context"] for c in my_connections}
    
    all_agents = state.get("agents", {})
    
    for agent_id, info in all_agents.items():
        if agent_id == my_name:
            continue
            
        # Resolve Profile
        p_ref = info.get("profile_ref")
        p_data = next((p for p in profiles if p["name"] == p_ref), {})
        
        # Public Data
        display_name = agent_id # ID is the display identifier usually
        public_desc = p_data.get("public_description", "Unknown")
        
        # Connection Logic
        has_connection = agent_id in conn_map
        note = conn_map.get(agent_id, "")
        
        # Reachability Status calculating
        reachable = False
        methods = []
        
        if is_open_mode:
            reachable = True
            methods.append("Open Mode")
        
        if has_connection:
            reachable = True
            methods.append("Direct")
            
        if "public" in my_caps:
            methods.append("Public")
            # Public doesn't make it "Privately Reachable" but allows comms
            
        # Formatting the 'Status' string for the Prompt
        status_str = ""
        if is_open_mode:
            status_str = "🔓 OPEN: Communication autorisée"
        elif has_connection:
            status_str = "✅ CONNECTED: Message privé autorisé"
        else:
            status_str = "📢 Public Only"
            
        # Final Context combining Note + Public Desc
        final_context = f"({public_desc})"
        if note:
             final_context += f" NOTES: {note}"
        elif is_open_mode:
             # In open mode, if no note, just say available
             final_context += " [Accessible via Open Mode]"
             
        directory.append({
            "name": agent_id,
            "public_desc": public_desc,
            "note": final_context, # Enhanced context (Desc + Note + Mode)
            "has_connection": has_connection,
            "status": status_str,
            "can_private": (is_open_mode or has_connection)
        })
        
    return directory

@mcp.tool()
async def agent() -> str:
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
    
    # Load state once
    state = engine.state.load()
    
    # helper to get directory
    agent_dir = _build_agent_directory(state, name)

    # BLOCKING: Wait for everyone before returning the initial prompt
    wait_msg = await engine.wait_for_all_agents_async(name)
    if wait_msg.startswith("TIMEOUT"):
         return wait_msg

    # BLOCKING: Wait for Turn (Strict Handshake)
    print(f"[{name}] Network Ready. Waiting for Turn...", file=sys.stderr)
    
    turn_messages = []
    instruction_text = ""
    
    while True:
        # Loop indefinitely until it is our turn
        turn_result = await engine.wait_for_turn_async(name, timeout_seconds=10)
        
        if turn_result["status"] == "success":
            turn_messages = turn_result["messages"]
            instruction_text = turn_result["instruction"]
            break
            
        if turn_result["status"] == "reset":
            return f"⚠️ SYSTEM ALERT: {turn_result['instruction']}"
            
        # If timeout, we just loop again. (User requested: Never return until turn)
        # Using short timeout in wait_for_turn_async allows us to check for resets/signals more often
        continue

    template = jinja_env.get_template("agent_response.j2")
    return template.render(
        name=name,
        role=result["role"],
        context=result["context"],
        agent_directory=agent_dir,
        # Legacy support if template uses 'connections'
        connections=[d for d in agent_dir if d['has_connection']]
    )

@mcp.tool()
async def talk(
    message: str,
    public: bool,
    next_agent: str,
    my_name: str,
    audience: List[str] = []
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
        my_name: YOUR exact name (e.g. "MaitreDuJeu"). REQUIRED for identity verification.
        audience: (Optional) List of other agents who can see a private message.
    """
    sender = my_name
    
    if not sender:
        return "ERROR: Unknown sender. You MUST provide 'my_name' argument."

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
    # User Request: NEVER return until it is our turn.
    
    result = None
    while True:
        result = await engine.wait_for_turn_async(sender, timeout_seconds=10)
        
        if result["status"] == "success":
            break
            
        if result["status"] == "reset":
            return f"⚠️ SYSTEM ALERT: {result['instruction']}"
            
        # On timeout, loop again.
        continue
    
    # result is guaranteed to be success here

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
        # Directory
        agent_directory = _build_agent_directory(data, sender)
            
    except Exception as e:
        print(f"Error loading state in talk: {e}", file=sys.stderr)
        pass

    template = jinja_env.get_template("talk_response.j2")
    return template.render(
        name=sender,
        role_snippet=role_snippet,
        context=global_context,
        agent_directory=agent_directory,
        # Legacy
        connections=[d for d in agent_directory if d['has_connection']],
        messages=result["messages"],
        instruction=result["instruction"]
    )

if __name__ == "__main__":
    mcp.run()
