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

# Logger Setup
try:
    from src.utils.logger import get_logger
    logger = get_logger()
except ImportError:
    # Fallback to local import if structure is flat (though src.utils should be there)
    # Using sys.stderr if logger fails
    logger = None


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
    
    # Explicitly add "User" if connected (or if open mode?)
    # User Request: "Il devrait être absent du tableau des autres agents, sauf si sa relation est précisée."
    if "User" in conn_map:
        note = conn_map.get("User", "")
        directory.append({
            "name": "User",
            "public_desc": "L'Utilisateur (Humain)",
            "note": f"({note})",
            "has_connection": True,
            "status": "✅ CONNECTED: Message privé autorisé",
            "can_private": True
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
    to: str,
    audience: List[str] = []
) -> str:
    """
    MAIN COMMUNICATION TOOL.
    1. Posts your message.
    2. Passes the turn to 'to'.
    3. BLOCKS/SLEEPS until it is your turn again.
    
    Args:
        message: The content to speak.
        public: If true, everyone sees the message. If false, only 'to' and 'audience' see it.
        to: The name of the agent who should speak next. (The message is always visible to them).
        audience: (Optional) List of other agents who can see a Private message.
    """
    # 0. Resolve Sender Identity using Session
    global SESSION_AGENT_NAME
    sender = SESSION_AGENT_NAME
    
    if not sender:
         error_msg = "CRITICAL ERROR: 'SESSION_AGENT_NAME' is not set. You must call the 'agent()' tool FIRST to register your identity before speaking."
         if logger: logger.error("SYSTEM", error_msg, "talk_tool_check")
         return error_msg

    next_agent = to
    
    if logger:
        logger.log("ACTION", sender, f"talking -> {next_agent} (Public: {public})", {"message": message, "audience": audience})
    else:
        print(f"[{sender}] talking -> Next: {next_agent}", file=sys.stderr)
    
    # 1. Post Message
    post_result = engine.post_message(sender, message, public, next_agent, audience)
    
    # Check for DENIED action
    if post_result.startswith("🚫"):
        if logger: logger.log("DENIED", "System", post_result, {"target": sender})
        # Return the error directly so the agent can retry
        return post_result
        
    if logger: logger.log("SUCCESS", "System", f"Message posted: {post_result}")
    else: print(f"Post Success: {post_result}", file=sys.stderr)
    
    # SPECIAL: User Turn Handling
    if next_agent == "User":
        if logger: logger.log("TURN", "System", "Turn passed to USER. Agent retains control for feedback.")
        # Do NOT block. Return special message immediately.
        # Construct the response using the template but with a specific instruction.
        
        try:
            data = engine.state.load()
            role_snippet = data["agents"][sender]["role"]
            global_context = data.get("config", {}).get("context", "")
            agent_directory = _build_agent_directory(data, sender)
        except Exception as e:
            if logger: logger.error(sender, f"Error loading state in talk (User): {e}")
            else: print(f"Error loading state in talk (User): {e}", file=sys.stderr)
            role_snippet = "Unknown"
            global_context = ""
            agent_directory = []

        template = jinja_env.get_template("talk_response.j2")
        
        # User defined message:
        user_feedback_msg = "Message bien envoyé à l'utilisateur, il vous répondra en temps voulu. En attendant, continuez votre travail d'agent en appelant un agent suivant."
        
        rendered = template.render(
            name=sender,
            role_snippet=role_snippet,
            context=global_context,
            agent_directory=agent_directory,
            connections=[d for d in agent_directory if d['has_connection']],
            messages=[],
            instruction=f"✅ {user_feedback_msg}" # Override instruction
        )
        return rendered

    # 2. Smart Block (Wait for Turn)
    # The turn has passed to next_agent. We now wait until it comes back to 'sender'.
    
    result = None
    while True:
        result = await engine.wait_for_turn_async(sender, timeout_seconds=10)
        
        if result["status"] == "success":
            if logger: logger.log("TURN", sender, "It is my turn again.")
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
    agent_directory = [] # Fix: Initialize empty list before try block to avoid UnboundLocalError
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
        if logger: logger.error(sender, f"Error loading state in talk: {e}")
        else: print(f"Error loading state in talk: {e}", file=sys.stderr)
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
