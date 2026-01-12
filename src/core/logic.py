import time
import asyncio
from typing import Optional, List, Dict, Any
from .state import StateStore

class Engine:
    def __init__(self, state_store: StateStore = None):
        self.state = state_store or StateStore()

    def get_public_context(self) -> str:
        """Returns the public conversation history."""
        # Using a simple read since precision isn't critical for this
        try:
            data = self.state.load()
            messages = data.get("messages", [])
            return "\n".join([f"[{m['from']}]: {m['content']}" for m in messages if m.get('public')])
        except:
            return ""

    def register_agent(self) -> Dict[str, Any]:
        """
        Registers a new agent by claiming a pending slot.
        Returns dict with keys: 'name', 'role', 'context', or 'error'.
        """
        result = {}
        
        def _register(state):
            # 1. Find a pending slot
            agents = state.get("agents", {})
            found_name = None
            found_data = None
            
            # Simple iteration - could be improved with priorities but First Come First Served is fine
            for name, data in agents.items():
                if data.get("status") == "pending_connection":
                    found_name = name
                    found_data = data
                    break
            
            if not found_name:
                result["error"] = "GAME FULL: No pending roles available. Please wait or contact Admin."
                return "Registration Failed: Full"
            
            # 2. Claim it
            agents[found_name]["status"] = "connected"
            
            # 2b. Announce it (System Message)
            # This fixes the "User sees nothing" bug
            sys_msg = {
                "from": "System",
                "content": f"🔵 **{found_name}** has joined the simulation.",
                "public": True,
                "target": "all",
                "audience": [],
                "timestamp": time.time()
            }
            state.setdefault("messages", []).append(sys_msg)
            
            # 3. Prepare Return Response
            config = state.get("config", {})
            result["name"] = found_name
            result["role"] = found_data.get("role", "Unknown Role")
            result["context"] = config.get("context", "")
            
            return f"Agent connected as '{found_name}'"

        self.state.update(_register)
        
        # LOGGING
        import sys
        print(f"[Logic] Register result for '{result.get('name', '??')}': {result}", file=sys.stderr)
        
        # If error was set inside update
        if "error" in result:
            return result
            
        return result

    def get_network_status(self, agent_name: str) -> Dict[str, Any]:
        """
        Helper to check connection status of the mesh.
        """
        state = self.state.load()
        agents = state.get("agents", {})
        config = state.get("config", {})
        
        total = config.get("total_agents", 0)
        connected = sum(1 for a in agents.values() if a.get("status") == "connected")
        
        other_agents = [n for n, d in agents.items() if d.get("status") == "connected" and n != agent_name]
        
        # Check if agent is valid
        if agent_name not in agents:
             return {"ready": False, "error": "Agent not found"}

        return {
            "ready": connected >= total,
            "total_required": total,
            "connected_count": connected,
            "other_agents": other_agents,
            "role": agents.get(agent_name, {}).get("role", "Unknown"),
            "context": config.get("context", "")
        }

    def wait_for_all_agents(self, name: str, timeout_seconds: int = 600) -> str:
        """
        Blocks until all agents are connected.
        Returns the System Context string.
        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            # Poll status
            info = self.get_network_status(name)
            
            if info.get("error"):
                return f"ERROR: {info['error']}"

            if info["ready"]:
                # Build context
                context = info["context"]
                other_agents_str = ", ".join(info["other_agents"])
                return (
                    f"CONTEXT: {context}\n\n"
                    f"You are {name}. Role: {info['role']}.\n"
                    f"Network is READY. Connected agents: {info['connected_count']}/{info['total_required']}.\n"
                    f"Peers: {other_agents_str}.\n"
                    "You may now speak if it is your turn."
                )
            
            time.sleep(2) # Polling interval
        
    async def wait_for_all_agents_async(self, name: str, timeout_seconds: int = 600) -> str:
        """
        Async version of wait_for_all_agents.
        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            # Poll status (Sync load is fine as it uses LOCK_NB now)
            # BUT we must use to_thread because state.load() might sleep (time.sleep) on lock contention
            info = await asyncio.to_thread(self.get_network_status, name)
            
            if info.get("error"):
                return f"ERROR: {info['error']}"

            if info["ready"]:
                # Build context
                context = info["context"]
                other_agents_str = ", ".join(info["other_agents"])
                return (
                    f"CONTEXT: {context}\n\n"
                    f"You are {name}. Role: {info['role']}.\n"
                    f"Network is READY. Connected agents: {info['connected_count']}/{info['total_required']}.\n"
                    f"Peers: {other_agents_str}.\n"
                    "You may now speak if it is your turn."
                )
            
            await asyncio.sleep(2) # Non-blocking Sleep
        
        return "TIMEOUT: Waiting for other agents took too long. Please retry agent() tool."

    def post_message(self, from_agent: str, content: str, public: bool, next_agent: str, audience: List[str]) -> str:
        """
        Posts a message and updates the turn.
        Validates capabilities and connections before posting.
        """
        def _post(state):
            # 0. VALIDATION
            agents = state.get("agents", {})
            config = state.get("config", {})
            profiles = config.get("profiles", [])
            
            nonlocal next_agent
            if next_agent: next_agent = next_agent.strip()
            
            if not next_agent:
                return "🚫 ACTION DENIED: 'next_agent' cannot be empty. You must specify who speaks next (e.g., 'MaitreDuJeu')."
            
            # Sanitize audience
            nonlocal audience
            audience = [a.strip() for a in audience if a.strip()]

            sender_info = agents.get(from_agent, {})
            sender_profile_name = sender_info.get("profile_ref")
            
            # Find Sender Profile
            sender_profile = next((p for p in profiles if p["name"] == sender_profile_name), None)
            
            if not sender_profile:
                # Fallback: If no profile found (e.g. manual/legacy), we block unless strictness is off?
                # User asked for strict enforcement.
                # However, let's allow if the system is bootstrapping (e.g. Role assignment phase? No, talk is later).
                # Let's BLOCK unknown agents to force proper config.
                import sys
                print(f"[Logic] BLOCK: Agent '{from_agent}' has no profile.", file=sys.stderr)
                return f"🚫 ACTION DENIED: Agent '{from_agent}' has no valid profile configuration. Please ask Admin to configure you in the Cockpit."

            caps = sender_profile.get("capabilities", [])
            connections = sender_profile.get("connections", [])
            allowed_targets = {c["target"]: c["context"] for c in connections} # Profile Names
            
            # DEBUG
            import sys
            print(f"[Logic DEBUG] From: {from_agent}", file=sys.stderr)
            print(f"[Logic DEBUG] Profile: {sender_profile.get('name')} | Ref: {sender_profile_name}", file=sys.stderr)
            print(f"[Logic DEBUG] Caps: {caps}", file=sys.stderr) 
            
            # MERGE INSTANCE CONNECTIONS (Priority)
            # This is critical for agents like MJ who get dynamic connections injected at setup
            instance_connections = sender_info.get("connections", [])
            for c in instance_connections:
                # Instance connections target Agent IDs (e.g. "Habitant #1"), not Profile Names
                # We add them to allowed_targets so check_target passes
                allowed_targets[c["target"]] = c["context"]
            
            # A. Capability Checks
            is_open = "open" in caps

            if next_agent == from_agent:
                 return "🚫 ACTION DENIED: You cannot pass the turn to yourself. Please choose another agent."
            
            if from_agent in audience:
                 return "🚫 ACTION DENIED: You cannot include yourself in the audience."
            
            # Prevent including Next Agent in Audience (Redundant/Confusing)
            if next_agent and next_agent in audience:
                return f"🚫 ACTION DENIED: '{next_agent}' is already the main recipient (next turn). Do not include them in the 'audience' list."

            if public and "public" not in caps and not is_open:
                return f"🚫 ACTION DENIED: You do not have the 'public' capability. You must send a Private message to a specific target."
            
            if not public and "private" not in caps and not is_open:
                 return f"🚫 ACTION DENIED: You do not have the 'private' capability. You must speak Publicly."
            
            if audience and "audience" not in caps and not is_open:
                 return f"🚫 ACTION DENIED: You do not have the 'audience' capability. You cannot cc additional agents."
            
            # B. Connection Checks (Skip if OPEN or sending to USER)
            # Special bypass for "User" if checking connections? 
            # Actually, we might want to enforce having a connection to "User" if we want to be strict.
            # But the user request says: "Il devrait être absent du tableau des autres agents, sauf si sa relation est précisée."
            # So implies connection is needed in profile to talk to User.
            
            if "open" not in caps:
                # Helper to check one target
                def check_target(t_name):
                    # Handle "User" special case
                    if t_name == "User":
                        # Must have a connection to "User" (profile or instance)
                        # We check allowed_targets below
                        if "User" in allowed_targets:
                            return None
                        return "No established connection to 'User'"

                    # target instance name (e.g. Wolf_1) -> profile (Wolf)
                    t_info = agents.get(t_name)
                    if not t_info:
                        return f"Unknown agent '{t_name}'"
                    t_prof = t_info.get("profile_ref")
                    
                    # Check 1: Is the specific Agent ID allowed? (Instance Connection)
                    if t_name in allowed_targets:
                        return None
                        
                    # Check 2: Is the Profile allowed? (Profile Connection)
                    if t_prof not in allowed_targets:
                         return f"Not connected to '{t_prof}' or specific agent '{t_name}'"
                    return None
                    
                # 1. Check Primary Target (Next Agent)
                # Note: next_agent is mandatory in talk tool.
                if next_agent:
                    err = check_target(next_agent)
                    if err:
                        # Construct helpful table
                        help_msg = "\nAllowed Connections:\n"
                        for t, ctx in allowed_targets.items():
                            help_msg += f"- {t}: {ctx}\n"
                        return f"🚫 ACTION DENIED: You are not authorized to speak to '{next_agent}' ({err}).\n{help_msg}"
                
                # 2. Check Audience
                for aud in audience:
                    err = check_target(aud)
                    if err:
                        return f"🚫 ACTION DENIED: You are not authorized to include '{aud}' in audience ({err})."

            # 1. Add message
            msg = {
                "from": from_agent,
                "content": content,
                "public": public,
                "target": next_agent,  # Explicit target for private filtering
                "audience": audience,
                "timestamp": time.time()
            }
            state.setdefault("messages", []).append(msg)
            
            # 2. Update Turn
            # Special Case: If sending to 'User', we do NOT pass the turn. The agent keeps it.
            # "Message bien envoyé à l'utilisateur... En attendant, continuez votre travail"
            
            if next_agent == "User":
                # Do not change turn
                import sys
                print(f"[Logic] USER MESSAGE: {from_agent} -> User. Turn remains with {from_agent}.", file=sys.stderr)
                return "Message sent to User. You still have the turn."
            else:
                old_turn = state["turn"].get("current")
                state["turn"]["current"] = next_agent
                state["turn"]["next"] = None # Consumed
                
                import sys
                print(f"[Logic] TURN CHANGE: {old_turn} -> {next_agent} (Sender: {from_agent})", file=sys.stderr)
                
                return f"Message posted. Next speaker is {next_agent}."
        
        return self.state.update(_post)

    def wait_for_turn(self, agent_name: str, timeout_seconds: int = 60) -> Dict[str, Any]:
        """
        Blocks until it is this agent's turn.
        Returns dict with keys: 'status' (success/timeout/reset), 'messages' (list), 'instruction' (str).
        """
        start_time = time.time()
        
        # 0. Capture current conversation ID to detect resets
        try:
            initial_state = self.state.load()
            current_conversation_id = initial_state.get("conversation_id")
        except Exception:
            current_conversation_id = None

        while time.time() - start_time < timeout_seconds:
            try:
                data = self.state.load()
            except Exception:
                time.sleep(1)
                continue
            
            # 1. Check for RESET
            new_conversation_id = data.get("conversation_id")
            if current_conversation_id and new_conversation_id != current_conversation_id:
                return {
                    "status": "reset",
                    "messages": [],
                    "instruction": "SYSTEM RESET: THe conversation has been reset by the user. Forget everything. Re-read your Role and Context."
                }
                
            current_turn = data.get("turn", {}).get("current")
            
            if current_turn == agent_name:
                # It's my turn!
                messages = data.get("messages", [])
                
                # 2. History Delta Logic: Get messages since my last turn
                # Find the index of the last message sent by ME
                last_my_index = -1
                for i, m in enumerate(messages):
                    if m.get("from") == agent_name:
                        last_my_index = i
                
                # If I have never spoken, this is my first turn (or re-entry). 
                # To be safe, we give full history (or maybe a reasonable startup window? No, full history is safer for context).
                # If last_my_index is -1, we slice from 0 (start).
                # If last_my_index is 5, we slice from 6 (next message).
                start_slice_index = last_my_index + 1
                recent_messages = messages[start_slice_index:]

                # 3. Filter for Visibility on this Delta
                # Visible = Public OR (Private AND (To Me OR From Me OR In Audience))
                visible_messages = []
                for m in recent_messages:
                    is_public = m.get("public", True)
                    sender = m.get("from")
                    target = m.get("target")
                    audience = m.get("audience", [])
                    
                    if is_public:
                        visible_messages.append(m)
                    elif sender == agent_name or target == agent_name or agent_name in audience:
                        visible_messages.append(m)
                
                # Build Strategic Advice from Connections
                agents = data.get("agents", {})
                config = data.get("config", {})
                
                my_info = agents.get(agent_name, {})
                profile_ref = my_info.get("profile_ref")
                
                advice_text = ""
                if profile_ref:
                    profiles = config.get("profiles", [])
                    profile = next((p for p in profiles if p["name"] == profile_ref), None)
                    
                    if profile and profile.get("connections"):
                        advice_text = "\n\n--- STRATEGIC ADVICE ---\n"
                        advice_text += "Based on your connections, here is how you should interact with others:\n"
                        
                        for conn in profile["connections"]:
                            target_profile = conn.get("target")
                            ctx = conn.get("context")
                            
                            # Resolve Target Profile -> Active Agent IDs
                            matching_agents = [
                                aid for aid, adata in agents.items() 
                                if adata.get("profile_ref") == target_profile and aid != agent_name
                            ]
                            
                            if matching_agents:
                                names_str = ", ".join(matching_agents)
                                advice_text += f"- **{target_profile}** is represented by: **{names_str}**. Strategy: {ctx}\n"
                            else:
                                # Connection exists but no agent with this role is currently active/other than me
                                advice_text += f"- **{target_profile}**: No other active agents found. Strategy: {ctx}\n"

                        advice_text += "------------------------"

                return {
                    "status": "success",
                    "messages": visible_messages, # FULL Delta, no truncation
                    "instruction": f"It is your turn. Speak.{advice_text}"
                }
            
            time.sleep(1)
            
        return {
            "status": "timeout",
            "messages": [],
            "instruction": "Still waiting for turn. connection_timeout_imminent. CALL THIS TOOL AGAIN IMMEDIATELY."
        }

    async def wait_for_turn_async(self, agent_name: str, timeout_seconds: int = 60) -> Dict[str, Any]:
        """
        Async version of wait_for_turn.
        """
        start_time = time.time()
        
        try:
            # Run blocking load() in a separate thread
            initial_state = await asyncio.to_thread(self.state.load)
            current_conversation_id = initial_state.get("conversation_id")
        except Exception:
            current_conversation_id = None

        while time.time() - start_time < timeout_seconds:
            try:
                # Run blocking load() in a separate thread
                data = await asyncio.to_thread(self.state.load)
            except Exception:
                await asyncio.sleep(1)
                continue
            
            # 1. Check for RESET
            new_conversation_id = data.get("conversation_id")
            if current_conversation_id and new_conversation_id != current_conversation_id:
                return {
                    "status": "reset",
                    "messages": [],
                    "instruction": "SYSTEM RESET: THe conversation has been reset by the user. Forget everything. Re-read your Role and Context."
                }
                
            current_turn = data.get("turn", {}).get("current")
            
            if current_turn == agent_name:
                # Reuse logic from sync version (code duplication is acceptable for safety here vs refactoring everything)
                messages = data.get("messages", [])
                
                # 2. History Delta Logic: Get messages since my last turn
                last_my_index = -1
                for i, m in enumerate(messages):
                    if m.get("from") == agent_name:
                        last_my_index = i
                
                start_slice_index = last_my_index + 1
                recent_messages = messages[start_slice_index:]

                # 3. Filter for Visibility
                visible_messages = []
                for m in recent_messages:
                    is_public = m.get("public", True)
                    sender = m.get("from")
                    target = m.get("target")
                    audience = m.get("audience", [])
                    
                    if is_public:
                        visible_messages.append(m)
                    elif sender == agent_name or target == agent_name or agent_name in audience:
                        visible_messages.append(m)
                
                agents = data.get("agents", {})
                config = data.get("config", {})
                my_info = agents.get(agent_name, {})
                profile_ref = my_info.get("profile_ref")
                
                advice_text = ""
                if profile_ref:
                    profiles = config.get("profiles", [])
                    profile = next((p for p in profiles if p["name"] == profile_ref), None)
                    if profile and profile.get("connections"):
                        advice_text = "\n\n--- STRATEGIC ADVICE ---\nBased on your connections, here is how you should interact with others:\n"
                        for conn in profile["connections"]:
                            target_profile = conn.get("target")
                            ctx = conn.get("context")
                            matching_agents = [aid for aid, adata in agents.items() if adata.get("profile_ref") == target_profile and aid != agent_name]
                            if matching_agents:
                                names_str = ", ".join(matching_agents)
                                advice_text += f"- **{target_profile}** is represented by: **{names_str}**. Strategy: {ctx}\n"
                            else:
                                advice_text += f"- **{target_profile}**: No other active agents found. Strategy: {ctx}\n"
                        advice_text += "------------------------"

                return {
                    "status": "success",
                    "messages": visible_messages,
                    "instruction": f"It is your turn. Speak.{advice_text}"
                }
            
            await asyncio.sleep(1) # Non-blocking Sleep
            
        return {
            "status": "timeout",
            "messages": [],
            "instruction": "Still waiting for turn. connection_timeout_imminent. CALL THIS TOOL AGAIN IMMEDIATELY."
        }
