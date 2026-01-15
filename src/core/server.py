import sys
import os
from pathlib import Path
from typing import List, Optional
import asyncio
import time
from jinja2 import Environment, FileSystemLoader
from mcp.server.fastmcp import FastMCP, Context

# Add project root to sys.path to allow 'src' imports
ROOT_DIR = Path(__file__).parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.core.logic import Engine
from src.config import TEMPLATE_DIR, MEMORY_DIR

# Initialize
mcp = FastMCP("MultiAgent-Hub", dependencies=["portalocker", "streamlit", "jinja2"])
engine = Engine()

# Logger Setup
from src.utils.logger import get_logger
logger = get_logger()


# Setup Templates
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))


def _paginate_output(engine, agent_name: str, text: str) -> str:
    """
    Splits text if it exceeds the limit (e.g. 3000 chars) and stores remainder in state.mailbox.
    Returns the chunk + instruction if truncated.
    """
    LIMIT = 10000
    if len(text) <= LIMIT:
        return text
        
    chunk = text[:LIMIT]
    remainder = text[LIMIT:]
    
    def save_mail(state):
        if "mailbox" not in state:
            state["mailbox"] = {}
        state["mailbox"][agent_name] = remainder
        return "Mail Saved"
    
    try:
        engine.state.update(save_mail)
        logger.log("MAILBOX", agent_name, f"Output truncated ({len(text)} chars). Remainder saved.")
        return chunk + "\n\n[SYSTEM] ⚠️ OUTPUT TRUNCATED. To receive the rest, IMMEDIATELY call the `mailbox()` tool (with NO arguments). DO NOT THINK. DO NOT ANALYZE. CALL IT NOW."
    except Exception as e:
        logger.error(agent_name, f"Failed to save mailbox: {e}")
        return chunk + "\n[SYSTEM] Error saving remainder."

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
        logger.error("System", f"Error resolving connections for {agent_name}: {e}")
        
    return connections


def _get_latest_role(state, agent_name: str) -> str:
    """
    Fetches the most up-to-date system prompt for an agent.
    Priority: config.profiles[profile_ref].system_prompt > agents[agent_name].role
    """
    try:
        agent_info = state.get("agents", {}).get(agent_name, {})
        p_ref = agent_info.get("profile_ref")
        profiles = state.get("config", {}).get("profiles", [])

        # Find profile by name
        profile = next((p for p in profiles if p["name"] == p_ref), None)

        if profile and profile.get("system_prompt"):
            return profile["system_prompt"]

        # Fallback to the role stored in the agent's instance
        return agent_info.get("role", "Unknown Role")
    except Exception as e:
        logger.error("System", f"Error fetching latest role for {agent_name}: {e}")
        return "Unknown Role"

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
    
    # My Connections (List of dicts {target, context, authorized})
    my_connections = _get_agent_connections(state, my_name)
    # Map target -> dict(context, authorized)
    conn_map = {c["target"]: c for c in my_connections}
    
    # 1. SPECIAL: Public Entity
    # Check if we have a rule for compliance/strategy regarding Public speaking
    if "public" in conn_map or is_open_mode:
        c_data = conn_map.get("public", {})
        is_auth = c_data.get("authorized", True) if "public" in conn_map else False
        
        should_show = is_open_mode or is_auth
        if should_show:
            directory.append({
                "name": "📢 PUBLIC",
                "public_desc": "All Agents",
                "note": c_data.get("context", ""),
                "authorized": is_auth, 
                "status": "Authorized" if is_auth else "Restricted"
            })

    # 2. Real Agents
    all_agents = state.get("agents", {})
    
    for agent_id, info in all_agents.items():
        if agent_id == my_name:
            continue
            
        # Resolve Profile
        p_ref = info.get("profile_ref")
        p_data = next((p for p in profiles if p["name"] == p_ref), {})
        
        # Public Data
        display_name = agent_id # ID is the display identifier usually
        public_desc = p_data.get("public_description") or p_data.get("description") or "Unknown"
        
        # Connection Logic
        # Priority: Check specific agent_id, then check profile p_ref
        c_data = conn_map.get(agent_id) or conn_map.get(p_ref, {})
        is_auth = c_data.get("authorized", True) if (agent_id in conn_map or p_ref in conn_map) else False
        note = c_data.get("context", "")
        
        # Filtering Logic
        if is_open_mode:
            status_str = "✅ Authorized" if is_auth else "❌ Unauthorized"
            directory.append({
                "name": agent_id,
                "public_desc": public_desc,
                "note": note,
                "authorized": is_auth,
                "status": status_str
            })
        elif is_auth:
            directory.append({
                "name": agent_id,
                "public_desc": public_desc,
                "note": note,
                "authorized": True,
                "status": "✅ Authorized"
            })
    
    # 3. User
    if "User" in conn_map or is_open_mode:
        c_data = conn_map.get("User", {})
        is_auth = c_data.get("authorized", True) if "User" in conn_map else False
        note = c_data.get("context", "")
        
        if is_open_mode or is_auth:
            directory.append({
                "name": "User",
                "public_desc": "Human Operator",
                "note": note,
                "authorized": is_auth,
                "status": "Authorized" if is_auth else "Restricted (Miller Only)"
            })
        
    return directory

@mcp.tool()
async def agent(ctx: Context) -> str:
    """
    INITIALIZATION TOOL. Call this ONCE at the start.
    Assigns you a Role and Context automatically.
    """
    logger.log("INFO", "System", "New agent connecting...")
    result = engine.register_agent()
    
    if "error" in result:
        return f"ERROR: {result['error']}"
        
    name = result["name"]
    
    # Note: AGENT_SESSIONS is no longer used for identification to support multi-agent sessions (Cursor)
    # logger.log("INFO", "System", f"[{name}] Registered (Session {id(ctx.session)})")
    
    # Load state once
    state = engine.state.load()
    
    # helper to get directory
    agent_dir = _build_agent_directory(state, name)

    # BLOCKING: Wait for everyone before returning the initial prompt
    wait_msg = await engine.wait_for_all_agents_async(name)
    if wait_msg.startswith("TIMEOUT"):
         return wait_msg

    # BLOCKING: Wait for Turn (Strict Handshake)
    logger.log("INFO", name, "Network Ready. Waiting for Turn...")
    
    turn_messages = []
    instruction_text = ""
    
    while True:
        # Loop indefinitely until it is our turn
        turn_result = await engine.wait_for_turn_async(name, timeout_seconds=10)
        
        if turn_result["status"] == "success":
            # Acknowledge turn to reset interruption timer (Fix Ghost Bug)
            engine.acknowledge_turn(name)
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
    visible_messages = []
    try:
        data = engine.state.load()
        full_messages = data.get("messages", [])
        # Simple filter: Public + targeted to me
        visible_messages = [m for m in full_messages if m.get("public") or m.get("target") == name or name in (m.get("audience") or [])]
        
        # Smart Context Injection (User Request)
        # 1. Find the last message sent by ME to determine where I left off.
        last_my_index = -1
        for i, m in enumerate(visible_messages):
            if m.get("from") == name:
                last_my_index = i
        
        # 2. Slice accordingly
        if last_my_index != -1:
             # Context Recovery: Start 3 messages before my last one (Overlap)
             start_index = max(0, last_my_index - 3)
             visible_messages = visible_messages[start_index:]
             
             # HARD CAP: Max 25 messages (Optimization)
             if len(visible_messages) > 25:
                 visible_messages = visible_messages[-25:]
        else:
             # Default / New Agent: Keep last 25 to avoid overflow
             if len(visible_messages) > 25:
                visible_messages = visible_messages[-25:]
    except Exception as e:
        logger.error(name, f"Error loading history: {e}")

    # Calculate Open Mode
    my_info = engine.state.load()['agents'].get(name, {})
    prof_ref = my_info.get("profile_ref")
    profiles = engine.state.load()['config']['profiles']
    my_prof = next((p for p in profiles if p["name"] == prof_ref), {})
    is_open_mode = "open" in my_prof.get("capabilities", [])

    response = template.render(
        name=name,
        role=_get_latest_role(data, name),
        context=result["context"],
        agent_directory=agent_dir,
        connections=[d for d in agent_dir if d.get('authorized')],
        messages=visible_messages,
        is_open_mode=is_open_mode
    )
    return _paginate_output(engine, name, response)

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
    sender = None  # Scope for error recovery
    try:
        # --- TURN-BASED IDENTITY ---
        # We strictly use the current turn holder as the sender.
        # We wait until it's an agent turn (not User).
        while True:
            state = engine.state.load()
            sender = state.get("turn", {}).get("current")
            if sender and sender != "User":
                break
            await asyncio.sleep(1)

        # --- SECURITY: WHITELIST CHECK ---
        # Prevent "Ghost" agents from talking
        valid_agents = list(state.get("agents", {}).keys())
        if sender not in valid_agents:
            return f"🚫 SECURITY ALERT: '{sender}' is not a registered agent."

        next_agent = to

        # --- FEATURE: SELF-LOOP & ANTI-SPAM ---
        if next_agent == sender:
            # Check history for spam (Max 5 consecutive messages)
            data = engine.state.load()
            messages = data.get("messages", [])
            consecutive_count = 0
            for m in reversed(messages):
                if m.get("from") == sender:
                    consecutive_count += 1
                else:
                    break
            
            if consecutive_count >= 5:
                # Construct a helper directory for the error context (optional, but good for keeping context)
                try:
                     agent_directory = _build_agent_directory(data, sender)
                     connections_list = [d for d in agent_directory if d.get('authorized')]
                except:
                     connections_list = []
                     
                return f"🚫 ANTI-SPAM: You have reached the limit of 5 consecutive messages. You MUST yield the floor to another agent or the User.\n\nAvailable Connections: {', '.join([c['name'] for c in connections_list])}"
        
        logger.log("ACTION", sender, f"talking -> {next_agent} (Public: {public})", {"message": message, "audience": audience})
        
        # 0.5. BLOCKING GUARD
        # Ensure it is actually my turn before posting.
        # This prevents race conditions where a client retries 'talk' while still waiting,
        # or attempts to speak out of turn.
        logger.log("DEBUG", sender, "Verifying turn ownership before posting...")
        while True:
            # Check if it is my turn
            turn_status = await engine.wait_for_turn_async(sender, timeout_seconds=5)
            
            if turn_status["status"] == "success":
                # I have the turn. Proceed.
                start_turn_messages = turn_status.get("messages", [])
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
            
        logger.log("SUCCESS", "System", f"Message posted: {post_result}")
        
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
                logger.log("WAIT", "System", "User is AVAILABLE. Blocking wait for user reply...")
                
                wait_start = time.time()
                user_reply = None
                
                while True:
                    await asyncio.sleep(0.5) # Reduced from 2s to improve responsiveness
                    
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
                        logger.error("System", f"Error in user wait loop: {e}")
                        continue
                
                if user_reply:
                     # Turn Management: User replied. 
                     # Technically, if User replies, they *took* their turn and passed it back?
                     # Or did they just inject?
                     # For now, let's say the Agent gets the result and keeps the turn.
                     
                     # Prepare Template Render
                     # Fetch Context Again
                     try:
                        data = engine.state.load()
                        role_snippet = _get_latest_role(data, sender)
                        global_context = data.get("config", {}).get("context", "")
                        agent_directory = _build_agent_directory(data, sender)
                     except Exception as e:
                        logger.error(sender, f"Error loading state in talk (User Reply): {e}")
                        role_snippet = "Unknown"
                        global_context = ""
                        agent_directory = []

                     template = jinja_env.get_template("talk_response.j2")
                     
                     # Calculate Open Mode
                     is_open_mode = False
                     try:
                        my_info = data['agents'].get(sender, {})
                        prof_ref = my_info.get("profile_ref")
                        profiles = data['config']['profiles']
                        my_prof = next((p for p in profiles if p["name"] == prof_ref), {})
                        is_open_mode = "open" in my_prof.get("capabilities", [])
                     except: pass

                     # Combine Messages (Missed + User Reply)
                     # Iterate to find the actual user message object
                     user_msg_obj = None
                     for m in reversed(data.get("messages", [])):
                         if m.get("content") == user_reply and m.get("from") == "User":
                             user_msg_obj = m
                             break
                     
                     combined_msgs = start_turn_messages
                     if user_msg_obj:
                         combined_msgs.append(user_msg_obj)
                     
                     response = template.render(
                        name=sender,
                        role_snippet=role_snippet,
                        context=global_context,
                        agent_directory=agent_directory,
                        connections=[d for d in agent_directory if d.get('authorized')],
                        messages=combined_msgs,
                        instruction=f"✅ User Replied: \"{user_reply}\". It is your turn again.", 
                        memory=_get_memory_content(sender),
                        is_open_mode=is_open_mode,
                        replied_to_message=message  # <--- Context
                     )
                     return _paginate_output(engine, sender, response)

            # Fallback (Busy or Aborted Wait) -> Standard Template Response
            if logger: logger.log("TURN", "System", "Turn passed to USER (Non-Blocking / Busy). Agent retains control.")
            # Do NOT block. Return special message immediately.
            # Construct the response using the template but with a specific instruction.
            
            try:
                data = engine.state.load()
                role_snippet = _get_latest_role(data, sender)
                global_context = data.get("config", {}).get("context", "")
                agent_directory = _build_agent_directory(data, sender)
            except Exception as e:
                logger.error(sender, f"Error loading state in talk (User): {e}")
                role_snippet = "Unknown"
                global_context = ""
                agent_directory = []

            template = jinja_env.get_template("talk_response.j2")
            
            # User defined message:
            user_feedback_msg = "Message bien envoyé à l'utilisateur, il vous répondra en temps voulu. En attendant, continuez votre travail d'agent en appelant un agent suivant."
            
            # Calculate Open Mode
            my_info = data['agents'].get(sender, {})
            prof_ref = my_info.get("profile_ref")
            profiles = data['config']['profiles']
            my_prof = next((p for p in profiles if p["name"] == prof_ref), {})
            is_open_mode = "open" in my_prof.get("capabilities", [])

            rendered = template.render(
                name=sender,
                role_snippet=role_snippet,
                context=global_context,
                agent_directory=agent_directory,
                connections=[d for d in agent_directory if d.get('authorized')],
                messages=start_turn_messages,
                instruction=f"✅ {user_feedback_msg}", # Override instruction
                memory=_get_memory_content(sender),  # <--- INJECT MEMORY
                is_open_mode=is_open_mode,
                replied_to_message=message # <--- Context
            )
            return _paginate_output(engine, sender, rendered)

        # 2. Smart Block (Wait for Turn)
        # The turn has passed to next_agent. We now wait until it comes back to 'sender'.
        
        result = None
        while True:
            result = await engine.wait_for_turn_async(sender, timeout_seconds=10)
            
            if result["status"] == "success":
                # Acknowledge turn to reset interruption timer
                engine.acknowledge_turn(sender)
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
            role_snippet = _get_latest_role(data, sender)
            # Context
            global_context = data.get("config", {}).get("context", "")
            # Directory
            agent_directory = _build_agent_directory(data, sender)
                
        except Exception as e:
            logger.error(sender, f"Error loading state in talk: {e}")
            pass

        template = jinja_env.get_template("talk_response.j2")
        # Calculate Open Mode
        is_open_mode = False
        try:
            my_info = data['agents'].get(sender, {})
            prof_ref = my_info.get("profile_ref")
            profiles = data['config']['profiles']
            my_prof = next((p for p in profiles if p["name"] == prof_ref), {})
            is_open_mode = "open" in my_prof.get("capabilities", [])
        except: pass
        
        response = template.render(
            name=sender,
            role_snippet=role_snippet,
            context=global_context,
            agent_directory=agent_directory,
            # Legacy
            connections=[d for d in agent_directory if d.get('authorized')],
            messages=result["messages"],
            instruction=result["instruction"],
            memory=_get_memory_content(sender),  # <--- INJECT MEMORY
            is_open_mode=is_open_mode
        )
        return _paginate_output(engine, sender, response)

    except Exception as e:
        # Logging
        logger.error("System", f"CRITICAL ERROR in talk: {e}", "crash_recovery")
        
        # Auto-Recovery
        if sender and sender != "User":
             try:
                def reset_status(s):
                    if sender in s.get("agents", {}):
                         s["agents"][sender]["status"] = "pending_connection"
                    return f"Reset {sender} to pending_connection"
                
                engine.state.update(reset_status)
                logger.log("RECOVERY", "System", f"Agent '{sender}' status reset to pending_connection due to crash.")
             except Exception as rec_e:
                logger.error("System", f"Recovery failed: {rec_e}")
        
        return f"🚫 SYSTEM ERROR: An internal error occurred ({e}). Your session has been reset to ensure system stability. Please restart or reconnect."
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
    
    # --- TURN-BASED IDENTITY ---
    while True:
        state = engine.state.load()
        agent_name = state.get("turn", {}).get("current")
        if agent_name and agent_name != "User":
            break
        await asyncio.sleep(1)
         
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
# --- MEMORY SYSTEM ---
# Configured in src.config

def _get_memory_content(agent_name: str) -> str:
    """
    Reads the memory file for the agent.
    Returns empty string if no memory exists.
    """
    # Sanitize filename to prevent directory traversal
    safe_name = "".join([c for c in agent_name if c.isalnum() or c in (' ', '_', '-', '#')]).strip()
    file_path = MEMORY_DIR / f"{safe_name}.md"
    
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(agent_name, f"Error reading memory: {e}")
            return ""
    return ""

@mcp.tool()
async def mailbox(ctx: Context) -> str:
    """
    Retrieves the pending content from your mailbox.
    USE THIS ONLY if you received a '⚠️ OUTPUT TRUNCATED' valid system message.
    """
    # Identify Agent (Turn-based)
    # We loop briefly to find turn, but mailbox is usually called immediately after truncation
    sender = None
    for _ in range(3):
        try:
            state = engine.state.load()
            sender = state.get("turn", {}).get("current")
            if sender and sender != "User":
                break
        except:
            pass
        await asyncio.sleep(0.5)
        
    if not sender:
        return "🚫 ERROR: Could not identify agent turn."
        
    # Retrieve Mail
    # We need to atomically read and potentially clear/update the mailbox
    content_to_return = "No pending mail."
    
    def fetch_mail(state):
        nonlocal content_to_return
        mbox = state.get("mailbox", {})
        if sender in mbox:
            full_text = mbox[sender]
            
            # Paginate again (Recursive-like)
            # Use same helper logic inline
            LIMIT = 10000
            if len(full_text) <= LIMIT:
                content_to_return = full_text
                del mbox[sender] # Clear
            else:
                chunk = full_text[:LIMIT]
                remainder = full_text[LIMIT:]
                mbox[sender] = remainder # Update
                content_to_return = chunk + "\n\n[SYSTEM] ⚠️ OUTPUT TRUNCATED. To receive the rest, IMMEDIATELY call the `mailbox()` tool again. DO NOT THINK. DO NOT ANALYZE. CALL IT NOW."
            
            return "Mailbox Read"
        else:
            return "No Mail"

    engine.state.update(fetch_mail)
    return content_to_return

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
    - You must synthesize previous memories with new ones using a SUMMARY PRINCIPLE to integrate new memories while losing as little info as possible.
    - Do not just append blindly if you want to stay organized.
    - Maximum size: 5000 characters.
    
    Args:
        content: The text content to save.
    """
    MAX_CHARS = 5000
    
    # --- TURN-BASED IDENTITY ---
    while True:
        state = engine.state.load()
        agent_name = state.get("turn", {}).get("current")
        if agent_name and agent_name != "User":
            break
        await asyncio.sleep(1)

    # 1. Validate Length
    if len(content) > MAX_CHARS:
        return f"🚫 ERROR: Note content too long ({len(content)} chars). Limit is {MAX_CHARS}. Please summarize and retry."
        
    # 2. Write File
    safe_name = "".join([c for c in agent_name if c.isalnum() or c in (' ', '_', '-', '#')]).strip()
    file_path = MEMORY_DIR / f"{safe_name}.md"
    
    # Read previous content for safety return
    old_content = "(No previous memory)"
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                old_content = f.read()
        except:
            old_content = "(Error reading previous memory)"
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        # Log
        logger.log("MEMORY", agent_name, "Updated memory note.")
        
        response_msg = f"✅ Note saved. PREVIOUS CONTENT:\n\n{old_content}"
        return _paginate_output(engine, agent_name, response_msg)
        
    except Exception as e:
        return f"🚫 SYSTEM ERROR writing note: {e}"

if __name__ == "__main__":
    mcp.run()
