from mcp.server.fastmcp import FastMCP, Context
import sys
import os
from typing import List, Optional
from jinja2 import Environment, FileSystemLoader
import asyncio

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

# Global Session Map: keys are session objects (or IDs), values are Agent Names
AGENT_SESSIONS = {}

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
async def agent(ctx: Context) -> str:
    """
    INITIALIZATION TOOL. Call this ONCE at the start.
    Assigns you a Role and Context automatically.
    """
    print(f"New agent connecting...", file=sys.stderr)
    result = engine.register_agent()
    
    if "error" in result:
        return f"ERROR: {result['error']}"
        
    name = result["name"]
    
    # Session Binding (Simplified for User Preference)
    # We still track sessions for basic transport validity, but we won't warn about collisions
    # as single-pipe local simulations are a valid use case.
    AGENT_SESSIONS[ctx.session] = name
    print(f"[{name}] Registered (Session {id(ctx.session)})", file=sys.stderr)
    
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
    
    # Get History for Context
    # Access state directly:
    try:
        data = engine.state.load()
        full_messages = data.get("messages", [])
        # Simple filter: Public + targeted to me
        # For a new agent, maybe just Public messages?
        visible_messages = [m for m in full_messages if m.get("public") or m.get("target") == name or name in m.get("audience", [])]
    except:
        visible_messages = []

    return template.render(
        name=name,
        role=result["role"],
        context=result["context"],
        agent_directory=agent_dir,
        connections=[d for d in agent_dir if d['has_connection']],
        messages=visible_messages
    )

@mcp.tool()
async def talk(
    message: str,
    public: bool,
    to: str,
    ctx: Context,
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
    # 0. Resolve Sender Identity
    sender = None
    
    # Session Lookup
    try:
        sender = AGENT_SESSIONS.get(ctx.session)
    except Exception:
        sender = None
        
    # --- SMART INFERENCE (Turn-Based Identity) ---
    # In single-pipe simulations, the Session ID is shared and ambiguous.
    # However, since agents act sequentially, the caller is implied to be the Current Turn Holder.
    # We prioritize this inference to resolve collisions transparently.
    
    current_turn = engine.state.load().get("turn", {}).get("current")
    if current_turn and (not sender or sender != current_turn):
         # Implicitly trust: If it's your turn, and you are calling talk(), you are the turn holder.
         sender = current_turn
             
    if not sender:
         return "🚫 ERROR: Session not recognized. You must call 'agent()' first to register your identity."

    next_agent = to
    
    if logger:
        logger.log("ACTION", sender, f"talking -> {next_agent} (Public: {public})", {"message": message, "audience": audience})
    else:
        print(f"[{sender}] talking -> Next: {next_agent}", file=sys.stderr)
    
    # 0.5. BLOCKING GUARD
    # Ensure it is actually my turn before posting.
    # This prevents race conditions where a client retries 'talk' while still waiting,
    # or attempts to speak out of turn.
    print(f"[{sender}] Verifying turn ownership before posting...", file=sys.stderr)
    while True:
        # Check if it is my turn
        turn_status = await engine.wait_for_turn_async(sender, timeout_seconds=5)
        
        if turn_status["status"] == "success":
            # I have the turn. Proceed.
            break
        elif turn_status["status"] == "reset":
             return f"⚠️ SYSTEM ALERT: {turn_status['instruction']}"
        
        # Otherwise, wait loop.
        if logger: 
            # Log only periodically to avoid noise
            # import time
            # if int(time.time()) % 10 == 0:
            #      logger.log("WAIT", sender, "Blocking action until turn is acquired...")
            pass
        # Continue loop
        
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
        is_user_available = False
        try:
            # Check availability config
            data = engine.state.load()
            config = data.get("config", {})
            # Default to 'busy' if not set, to be non-blocking by default
            is_user_available = (config.get("user_availability") == "available")
        except:
            pass

        # If Available, we BLOCK and wait for User Reply
        if is_user_available:
            if logger: logger.log("WAIT", "System", "User is AVAILABLE. Blocking wait for user reply...")
            else: print(f"[{sender}] User AVAILABLE. Waiting for reply...", file=sys.stderr)
            
            wait_start = time.time()
            user_reply = None
            
            while True:
                await asyncio.sleep(2)
                
                # Reload State
                try:
                    data = engine.state.load()
                    messages = data.get("messages", [])
                    config = data.get("config", {})
                    
                    # 1. Critical Check: Did user switch to BUSY?
                    curr_avail = (config.get("user_availability") == "available")
                    if not curr_avail:
                        if logger: logger.log("WAIT_ABORT", "System", "User switched to BUSY. Aborting wait.")
                        break # Fallback to standard non-blocking response
                        
                    # 2. Check for Reset
                    new_cid = data.get("conversation_id")
                    # (Assuming capturing cid logic is similar to wait_for_turn, simplified here)
                    
                    # 3. Check for User Message
                    # Look for message FROM User where timestamp > wait_start
                    for m in reversed(messages):
                        if m.get("from") == "User" and m.get("timestamp", 0) > wait_start:
                            user_reply = m.get("content", "")
                            break
                    
                    if user_reply:
                        break
                        
                except Exception as e:
                    print(f"Error in user wait loop: {e}", file=sys.stderr)
                    continue
            
            if user_reply:
                 # Turn Management: User replied. 
                 # Technically, if User replies, they *took* their turn and passed it back?
                 # Or did they just inject?
                 # For now, let's say the Agent gets the result and keeps the turn.
                 return f"User Replied: \"{user_reply}\""

        # Fallback (Busy or Aborted Wait) -> Standard Template Response
        if logger: logger.log("TURN", "System", "Turn passed to USER (Non-Blocking / Busy). Agent retains control.")
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
            instruction=f"✅ {user_feedback_msg}", # Override instruction
            memory=_get_memory_content(sender)  # <--- INJECT MEMORY
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
        instruction=result["instruction"],
        memory=_get_memory_content(sender)  # <--- INJECT MEMORY
    )

@mcp.tool()
async def sleep(seconds: int, ctx: Context) -> str:
    """
    Pause execution for a specified duration by sleeping.
    Useful for waiting for external events or pacing execution.
    Maximum duration is 300 seconds (5 minutes).
    """
    MAX_SLEEP = 300
    warning = ""
    
    if seconds > MAX_SLEEP:
        warning = f"⚠️ WARNING: Requested sleep of {seconds}s exceeds limit. Capped at {MAX_SLEEP}s.\n"
        seconds = MAX_SLEEP
    
    # 0. Identify Agent (Trust Turn)
    try:
        agent_name = AGENT_SESSIONS.get(ctx.session)
    except Exception:
        agent_name = None
        
    current_turn = engine.state.load().get("turn", {}).get("current")
    if current_turn and (not agent_name or agent_name != current_turn):
         # Inference
         agent_name = current_turn
         
    # 1. Update Status to Sleeping
    if agent_name:
        def set_sleep(s):
            if agent_name in s.get("agents", {}):
                s["agents"][agent_name]["status"] = f"sleeping: {seconds}s"
            return "Status Updated"
        try:
            engine.state.update(set_sleep)
        except:
            pass
        
    await asyncio.sleep(seconds)
    
    # 2. Revert Status
    if agent_name:
        def wake_up(s):
            if agent_name in s.get("agents", {}):
                s["agents"][agent_name]["status"] = "connected"
            return "Status Updated"
        try:
            engine.state.update(wake_up)
        except:
            pass
            
    return f"{warning}✅ Slept for {seconds} seconds."

# --- MEMORY SYSTEM ---
MEMORY_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "memory")
# Fallback if running from root
if not os.path.exists(os.path.dirname(MEMORY_DIR)):
     MEMORY_DIR = os.path.abspath("assets/memory")

if not os.path.exists(MEMORY_DIR):
    os.makedirs(MEMORY_DIR, exist_ok=True)

def _get_memory_content(agent_name: str) -> str:
    """
    Reads the memory file for the agent.
    Returns empty string if no memory exists.
    """
    # Sanitize filename to prevent directory traversal
    safe_name = "".join([c for c in agent_name if c.isalnum() or c in (' ', '_', '-', '#')]).strip()
    file_path = os.path.join(MEMORY_DIR, f"{safe_name}.md")
    
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            if logger: logger.error(agent_name, f"Error reading memory: {e}")
            return ""
    return ""

@mcp.tool()
async def note(content: str, ctx: Context) -> str:
    """
    Manage your persistent memory.
    This tool OVERWRITES your existing memory file with the new content provided.
    
    USE THIS TO:
    - Maintain a roadmap or to-do list.
    - Synthesize observations and results.
    - Prepare for future turns.
    
    IMPORTANT:
    - The content of this note is re-injected into your context at the start of every turn (via 'talk').
    - You must synthesize previous memories with new ones; do not just append blindly if you want to stay organized.
    - Maximum size: 5000 characters.
    
    Args:
        content: The text content to save.
    """
    MAX_CHARS = 5000
    
    # 0. Identify Agent
    try:
        agent_name = AGENT_SESSIONS.get(ctx.session)
    except Exception:
        agent_name = None
    
    # --- SMART INFERENCE (Turn-Based Identity) ---
    current_turn = engine.state.load().get("turn", {}).get("current")
    if current_turn and (not agent_name or agent_name != current_turn):
         # Blindly trust the turn holder for notes as well
         agent_name = current_turn

    if not agent_name:
         return "🚫 ERROR: Session not recognized. You must call 'agent()' first to register your identity."
         
    # 1. Validate Length
    if len(content) > MAX_CHARS:
        return f"🚫 ERROR: Note content too long ({len(content)} chars). Limit is {MAX_CHARS}. Please summarize and retry."
        
    # 2. Write File
    safe_name = "".join([c for c in agent_name if c.isalnum() or c in (' ', '_', '-', '#')]).strip()
    file_path = os.path.join(MEMORY_DIR, f"{safe_name}.md")
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        # Log
        if logger: logger.log("MEMORY", agent_name, "Updated memory note.")
        return "✅ Note saved. This content will be provided to you in future turns."
        
    except Exception as e:
        return f"🚫 SYSTEM ERROR writing note: {e}"

if __name__ == "__main__":
    mcp.run()
