import time
import asyncio
from typing import Optional, List, Dict, Any
from .state import StateStore

class Engine:
    def __init__(self, state_store: StateStore = None):
        self.state = state_store or StateStore()
        try:
            from ..utils.logger import get_logger
            self.logger = get_logger()
        except ImportError:
            self.logger = None

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
            agents[found_name]["reload_active"] = False
            
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
        if self.logger:
            self.logger.log("REGISTER", result.get('name', '??'), f"Registration Result: {result}")
        else:
            print(f"[Logic] Register result for '{result.get('name', '??')}': {result}", file=sys.stderr)
        
        # If error was set inside update
        if "error" in result:
            if self.logger: self.logger.error("System", result["error"], "registration")
            return result
            
        return result

    def get_network_status(self, agent_name: str) -> Dict[str, Any]:
        """
        Helper to check connection status of the mesh.
        """
        state = self.state.load()
        agents = state.get("agents", {})
        config = state.get("config", {})
        
        # Robustness: use the actual number of agents defined in the state
        # rather than a potentially out-of-sync config value.
        total = len(agents) if agents else config.get("total_agents", 0)
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
        
    def acknowledge_turn(self, agent_name: str) -> None:
        """
        Updates the turn_start_time to now.
        Used when an agent successfully retrieves the turn, acknowledging they have seen all prior messages.
        """
        def _ack(state):
            # Only update if it is indeed this agent's turn to prevent hijacking
            if state.get("turn", {}).get("current") == agent_name:
                state["turn"]["turn_start_time"] = time.time()
                return "Turn Acknowledged"
            return "Turn Ack Failed: Not your turn"
        self.state.update(_ack)

    def _finalize_turn_transition(self, state, intended_next: str) -> str:
        """
        Internal helper to manage turn transitions.
        """
        turn_data = state.get("turn", {})
        old_turn = turn_data.get("current")

        # 1. Resume normal flow.
        final_next = intended_next
        if turn_data.get("pending_next"):
            final_next = turn_data["pending_next"]
            state["turn"]["pending_next"] = None
        
        state["turn"]["current"] = final_next
        state["turn"]["turn_start_time"] = time.time()
        
        if final_next == old_turn:
            state["turn"]["consecutive_count"] = turn_data.get("consecutive_count", 0) + 1
        else:
            state["turn"]["consecutive_count"] = 1
        
        import sys
        if self.logger:
            self.logger.log("TURN_CHANGE", "System", f"Turn passed to {final_next}")
        else:
            print(f"[Logic] TURN CHANGE: {old_turn} -> {final_next}", file=sys.stderr)
            
        return f"Turn is now: {final_next}."

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

    def post_message(self, from_agent: str, content: str, public: bool, next_agent: str, audience: List[str] = None) -> str:
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

            # --- RESOLVE AGENT ID FROM PROFILE ---
            if next_agent and next_agent not in agents and next_agent != "User":
                for aid, adata in agents.items():
                    if adata.get("profile_ref") == next_agent:
                        next_agent = aid
                        break # Use the first agent matching the profile
            # -------------------------------------
            
            if not next_agent:
                return "🚫 ACTION DENIED: 'next_agent' cannot be empty. You must specify who speaks next."
            
            if next_agent not in agents and next_agent != "User":
                 # Strict Existence Check (Fix for typos causing deadlocks)
                 return f"🚫 TARGET_NOT_FOUND: {next_agent}"

            sender_info = agents.get(from_agent, {})
            sender_profile_name = sender_info.get("profile_ref")
            
            # Find Sender Profile
            sender_profile = next((p for p in profiles if p["name"] == sender_profile_name), None)
            
            # Special bypass for "User" (Admin/Human)
            if from_agent == "User":
                sender_profile = {"name": "User", "capabilities": ["public", "private"], "connections": []}
            else:
                if not sender_profile:
                    return f"🚫 ACTION DENIED: Agent '{from_agent}' has no valid profile validation."

            caps = sender_profile.get("capabilities", [])
            connections = sender_profile.get("connections", [])
            # Map of authorized targets (profiles or specific IDs)
            allowed_targets = {c["target"]: c["context"] for c in connections if c.get("authorized", True)}
            
            # MERGE INSTANCE CONNECTIONS (Priority)
            instance_connections = sender_info.get("connections", [])
            for c in instance_connections:
                if c.get("authorized", True):
                    allowed_targets[c["target"]] = c["context"]
            
            # Anti-Ghost Check (Sprint 6)
            if from_agent != "User":
                turn_data = state.get("turn", {})
                turn_start = turn_data.get("turn_start_time", 0.0)
                last_user = turn_data.get("last_user_message_time", 0.0)
                
                # If User spoke AFTER turn started
                if last_user > turn_start:
                     # 2. Fetch missed messages (Fix Silence)
                     missed = [m for m in state.get("messages", []) if m.get("from") == "User" and m.get("timestamp", 0) > turn_start]
                     relevant = [m for m in missed if m.get("public") or m.get("target") == from_agent]
                     
                     if relevant:
                         # 1. Update Turn Start to unblock next attempt (Fix Deadlock)
                         state["turn"]["turn_start_time"] = time.time()
                         missed_text = "\n".join([f"- User: {m.get('content')}" for m in relevant])
                         return f"🚫 INTERACTION REJECTED: The User interrupted you with new messages:\n{missed_text}\n\nACTION: Core logic has reset your turn timer. Incorporate this new info and try again."

            if next_agent == from_agent:
                 # Allow self-loop with limit
                 consecutive = state["turn"].get("consecutive_count", 0)
                 old_turn = state["turn"].get("current")
                 if old_turn == from_agent and consecutive >= 5:
                     return "🚫 PROHIBITED: Self-loop limit reached (5/5). You cannot speak 6 times in a row. Please yield the turn."

            # A. Capability Checks
            # User Rule: "Tous les agents ne doivent pouvoir parler qu'en public." (Implies preference, but logic supports private if cap exists)
            
            if public and "public" not in caps and "public" not in allowed_targets:
                 # Note: allowed_targets usually lists generic "public" connection if explicit
                 return f"🚫 ACTION DENIED: You do not have the 'public' capability."
            
            if not public:
                 # Private Message
                 if "private" not in caps:
                      return f"🚫 ACTION DENIED: You do not have the 'private' capability. You can only speak publicly."
                 
                 # Check connection to target
                 # Helper to check one target
                 def check_target(t_name):
                    if t_name == "User":
                        if "User" in allowed_targets: return None
                        return "No established connection to 'User'"
                    t_info = agents.get(t_name)
                    if not t_info: return f"Unknown agent '{t_name}'"
                    t_prof = t_info.get("profile_ref")
                    if t_name in allowed_targets: return None
                    if t_prof in allowed_targets: return None
                    return f"Not connected to '{t_prof}'"
                 
                 err = check_target(next_agent)
                 if err:
                     return f"🚫 ACTION DENIED: You are not authorized to speak privately to '{next_agent}' ({err})."

            # 1. Add message
            msg = {
                "from": from_agent,
                "content": content,
                "public": public,
                "target": next_agent, 
                "audience": audience or [],
                "timestamp": time.time()
            }
            state.setdefault("messages", []).append(msg)
            
            # 2. Update Turn
            # Update Logic timestamps
            current_time = time.time()
            if from_agent == "User":
                state["turn"]["last_user_message_time"] = current_time
            
            # USE CENTRALIZED TRANSITION LOGIC
            transition_msg = self._finalize_turn_transition(state, next_agent)
            
            base_msg = f"Message posted. {transition_msg}"
            if state["turn"].get("current") == from_agent:
                base_msg += "\n[INFO] Il est possible de reprendre la parole après avoir envoyé un message."
            
            return base_msg
        
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
            
            # 0. Check for PAUSE
            if data.get("config", {}).get("paused"):
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
                
            # 1b. Check for Status Reset (Kicked/Reloaded)
            agent_data = data.get("agents", {}).get(agent_name, {})
            my_status = agent_data.get("status")
            if my_status == "pending_connection":
                    return {
                    "status": "reset",
                    "messages": [],
                    "instruction": "SYSTEM RESET: Your session has been terminated by the user. [TERMINATE_SESSION]\nThe loop has ended. You will be reloaded.\n1. Update memory via the `note` tool.\n2. STOP COMPLETELY. Do not call talk, agent, or sleep. Just terminate the conversation."
                }
            
            # 1c. Check for RELOAD
            if agent_data.get("reload_active"):
                return {
                    "status": "reset",
                    "messages": [],
                    "instruction": "SYSTEM ALERT: [RELOAD IN PROGRESS] You have been scheduled for a reload.\nThe loop has ended. You will be reloaded.\n1. Update memory via the `note` tool.\n2. STOP COMPLETELY. Do not call talk, agent, or sleep. Just terminate the conversation."
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
                # Context Recovery: Start 3 messages before my last one (Overlap)
                start_slice_index = max(0, last_my_index - 3)
                recent_messages = messages[start_slice_index:]

                # 3. Filter for Visibility on this Delta
                # Visible = Public OR (Private AND (Me==Sender OR Me==Target OR Me.Profile==Sender.Profile))
                visible_messages = []
                
                agents_map = data.get("agents", {})
                my_prof = agents_map.get(agent_name, {}).get("profile_ref")
                
                for m in recent_messages:
                    is_public = m.get("public", True)
                    sender = m.get("from")
                    target = m.get("target")
                    
                    if is_public:
                        visible_messages.append(m)
                        continue
                        
                    # Private Logic
                    if sender == agent_name or target == agent_name or agent_name in (m.get("audience") or []):
                        visible_messages.append(m)
                    elif my_prof:
                         sender_prof = agents_map.get(sender, {}).get("profile_ref")
                         if sender_prof and sender_prof == my_prof:
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
            
            # 0. Check for PAUSE
            if data.get("config", {}).get("paused"):
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
                
            # 1b. Check for Status Reset (Kicked/Reloaded)
            agent_data = data.get("agents", {}).get(agent_name, {})
            my_status = agent_data.get("status")
            if my_status == "pending_connection":
                 return {
                    "status": "reset",
                    "messages": [],
                    "instruction": "SYSTEM RESET: Your session has been terminated by the user. [TERMINATE_SESSION]\nThe loop has ended. You will be reloaded.\n1. Update memory via the `note` tool.\n2. STOP COMPLETELY. Do not call talk, agent, or sleep. Just terminate the conversation."
                }

            # 1c. Check for RELOAD
            if agent_data.get("reload_active"):
                return {
                    "status": "reset",
                    "messages": [],
                    "instruction": "SYSTEM ALERT: [RELOAD IN PROGRESS] You have been scheduled for a reload.\nThe loop has ended. You will be reloaded.\n1. Update memory via the `note` tool.\n2. STOP COMPLETELY. Do not call talk, agent, or sleep. Just terminate the conversation."
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
                
                # Context Recovery: Start 3 messages before my last one (Overlap)
                start_slice_index = max(0, last_my_index - 3)
                recent_messages = messages[start_slice_index:]

                # 3. Filter for Visibility
                # 3. Filter for Visibility on this Delta
                # Visible = Public OR (Private AND (Me==Sender OR Me==Target OR Me.Profile==Sender.Profile))
                visible_messages = []
                
                agents_map = data.get("agents", {})
                my_prof = agents_map.get(agent_name, {}).get("profile_ref")
                
                for m in recent_messages:
                    is_public = m.get("public", True)
                    sender = m.get("from")
                    target = m.get("target")
                    
                    if is_public:
                        visible_messages.append(m)
                        continue
                        
                    # Private Logic
                    if sender == agent_name or target == agent_name or agent_name in (m.get("audience") or []):
                        visible_messages.append(m)
                    elif my_prof:
                         sender_prof = agents_map.get(sender, {}).get("profile_ref")
                         if sender_prof and sender_prof == my_prof:
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
