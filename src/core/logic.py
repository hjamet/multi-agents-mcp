import time
import asyncio
import re
from typing import Optional, List, Dict, Any
from .state import StateStore
from ..config import STOP_INSTRUCTION, RELOAD_INSTRUCTION
from .models import TurnQueueItem


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
            # This fixes the "User sees nothing" bug and helps agents identify a fresh start
            sys_msg = {
                "from": "System",
                "content": f"🔵 **{found_name}** vient de se reconnecter.",
                "public": True, 
                "target": "All", 
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
            "context": config.get("context", ""),
            "language": config.get("language", "fr")
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

            # --- RELOAD/RESET CHECK ---
            try:
                data = self.state.load()
                agent_data = data.get("agents", {}).get(name, {})
                if agent_data.get("reload_active") or agent_data.get("status") == "pending_connection":
                    return "RELOAD_REQUIRED"
            except:
                pass
            # --------------------------

            if info["ready"]:
                # Build context
                lang = info.get("language", "fr")
                context = info["context"]
                other_agents_str = ", ".join(info["other_agents"])

                # i18n
                # Localized Strings (Simplified Replacement for i18n)
                if lang in ["fr", "French"]:
                     t_ctx_label = "CONTEXTE :"
                     t_you_are = f"Tu es {name}. Rôle : {info['role']}."
                     t_ready = f"Le réseau est PRÊT. Agents connectés : {info['connected_count']}/{info['total_required']}."
                     t_peers = f"Pairs : {other_agents_str}."
                     t_speak = "Tu peux maintenant parler si c'est ton tour."
                else:
                     t_ctx_label = "CONTEXT:"
                     t_you_are = f"You are {name}. Role: {info['role']}."
                     t_ready = f"Network is READY. Connected agents: {info['connected_count']}/{info['total_required']}."
                     t_peers = f"Peers: {other_agents_str}."
                     t_speak = "You may now speak if it is your turn."

                return (
                    f"{t_ctx_label} {context}\n\n"
                    f"{t_you_are}\n"
                    f"{t_ready}\n"
                    f"{t_peers}\n"
                    f"{t_speak}"
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

    def _finalize_turn_transition(self, state: Dict[str, Any], intended_next: str = None) -> str:
        """
        Manages turn transitions using the Priority Queue.
        Logic: Sort Queue (Count DESC, Time ASC) -> Pick Top -> Decrement -> Set Turn.
        If 'intended_next' is provided, it overrides the queue (used by User or Admin).
        """
        turn_data = state.get("turn", {})
        queue_raw = turn_data.get("queue", [])
        
        # Convert to objects
        queue = []
        for item in queue_raw:
            if isinstance(item, dict):
                queue.append(TurnQueueItem(**item))
            else:
                queue.append(item)

        next_agent = None

        if intended_next:
            next_agent = intended_next
            # If the intended agent was in the queue, reset their count to 0 (FIFO rule)
            existing = next((i for i in queue if i.name == next_agent), None)
            if existing:
                existing.count = 0
                queue.remove(existing)
        else:
            if not queue:
                state["turn"]["current"] = "User"
                state["turn"]["turn_start_time"] = time.time()
                state["turn"]["consecutive_count"] = 0
                return "Queue empty. Turn passed to User."

            # Sort and Pick
            queue.sort(key=lambda x: (-x.count, x.timestamp))
            next_item = queue[0]
            next_agent = next_item.name
            # Reset count to 0 when agent speaks (FIFO rule)
            next_item.count = 0
            queue.pop(0)

        # Serialize back
        state["turn"]["queue"] = [item.model_dump() for item in queue]
        
        # Update Turn State
        old_turn = turn_data.get("current")
        state["turn"]["current"] = next_agent
        state["turn"]["turn_start_time"] = time.time()
        
        if next_agent == old_turn:
            state["turn"]["consecutive_count"] = turn_data.get("consecutive_count", 0) + 1
        else:
            state["turn"]["consecutive_count"] = 1
            
        remaining_str = ", ".join([f"{i.name}({i.count})" for i in queue])
        return f"Turn passed to {next_agent}. Queue: [{remaining_str}]"

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

            # --- RELOAD/RESET CHECK ---
            try:
                data = await asyncio.to_thread(self.state.load)
                agent_data = data.get("agents", {}).get(name, {})
                if agent_data.get("reload_active") or agent_data.get("status") == "pending_connection":
                    return "RELOAD_REQUIRED"
            except:
                pass
            # --------------------------

            if info["ready"]:
                # Build context
                lang = info.get("language", "fr")
                context = info["context"]
                other_agents_str = ", ".join(info["other_agents"])

                # i18n
                # Localized Strings (Simplified Replacement for i18n)
                if lang in ["fr", "French"]:
                     t_ctx_label = "CONTEXTE :"
                     t_you_are = f"Tu es {name}. Rôle : {info['role']}."
                     t_ready = f"Le réseau est PRÊT. Agents connectés : {info['connected_count']}/{info['total_required']}."
                     t_peers = f"Pairs : {other_agents_str}."
                     t_speak = "Tu peux maintenant parler si c'est ton tour."
                else:
                     t_ctx_label = "CONTEXT:"
                     t_you_are = f"You are {name}. Role: {info['role']}."
                     t_ready = f"Network is READY. Connected agents: {info['connected_count']}/{info['total_required']}."
                     t_peers = f"Peers: {other_agents_str}."
                     t_speak = "You may now speak if it is your turn."

                return (
                    f"{t_ctx_label} {context}\n\n"
                    f"{t_you_are}\n"
                    f"{t_ready}\n"
                    f"{t_peers}\n"
                    f"{t_speak}"
                )
            
            await asyncio.sleep(2) # Non-blocking Sleep
        
        return "TIMEOUT: Waiting for other agents took too long. Please retry agent() tool."

    def _build_connections_table(self, from_agent: str, state: Dict[str, Any], allowed_targets: Dict[str, str]) -> str:
        """
        Helper to build a connections table showing who the agent can mention.
        """
        agents = state.get("agents", {})
        
        # Build list of mentionable agents
        mentionable = []
        
        # FIX BUG #6: Don't automatically add User, only if in allowed_targets
        # User is treated like any other target
        
        # Add allowed targets
        for target_name in allowed_targets.keys():
            # Check if it's a profile name or agent name
            if target_name in agents:
                mentionable.append(f"@{target_name}")
            elif target_name == "User":
                # User is a special case (not in agents dict)
                mentionable.append("@User")
            elif target_name != "public":
                # It's a profile name, find matching agents
                matching = [name for name, data in agents.items() 
                           if data.get("profile_ref") == target_name and name != from_agent]
                for m in matching:
                    mentionable.append(f"@{m}")
        
        if not mentionable:
            return "\n\n📋 **Your Connections**: None (you cannot mention anyone)"
        
        return f"\n\n📋 **Your Connections**: You can mention: {', '.join(sorted(set(mentionable)))}"

    def post_message(self, from_agent: str, content: str, public: bool, audience: List[str] = None) -> str:
        """
        Posts a message, parses mentions, updates queue, and transitions turn.
        """
        def _post(state):
            # 0. VALIDATION
            agents = state.get("agents", {})
            current_turn = state.get("turn", {}).get("current")
            
            # --- SECURITY: STRICT TURN CHECK ---
            if from_agent != "User" and current_turn != from_agent:
                 return f"🚫 SECURITY VIOLATION: Write Access Denied. It is '{current_turn}'s turn, not yours."

            config = state.get("config", {})
            profiles = config.get("profiles", [])
            
            sender_info = agents.get(from_agent, {})
            sender_profile_name = sender_info.get("profile_ref")
            
            # Find Sender Profile
            sender_profile = next((p for p in profiles if p["name"] == sender_profile_name), None)
            
            # User Bypass
            if from_agent == "User":
                sender_profile = {"name": "User", "capabilities": ["public", "private"], "connections": []}
            elif not sender_profile:
                 return f"🚫 IDENTITY ERROR: Profile not found for {from_agent}."

            caps = sender_profile.get("capabilities", [])
            allowed_targets = {}
            
            # Build Allow List
            # Profile Connections
            for c in sender_profile.get("connections", []):
                if c.get("authorized", True):
                    allowed_targets[c["target"]] = c.get("context", "")
            
            # Instance Connections (Priority)
            for c in sender_info.get("connections", []):
                if c.get("authorized", True):
                    allowed_targets[c["target"]] = c.get("context", "")


            # --- MENTIONS PARSING ---
            # FIX BUG #3 (User Suggestion): Character-by-character parsing instead of regex
            # FIX BUG #9: Support backslash escaping (\@) to allow referencing agents without mentioning
            # Algorithm:
            # 1. Find all @ symbols
            # 2. Ignore those in backticks
            # 3. Ignore those preceded by backslash (\@)
            # 4. For each @, look at next X chars (X = longest agent name)
            # 5. Check if substring matches any agent name
            # 6. Take longest match if multiple exist
            
            # Build list of all possible agent names (including User)
            # FIX: Also include profile references (e.g. Agent_B) and map them to full names
            profile_map = {}
            for name, data in agents.items():
                pref = data.get("profile_ref")
                if pref:
                    profile_map[pref] = name
            
            # Parsing Targets: Full Names + Profile Refs + User
            all_targets = list(agents.keys()) + ["User"] + list(profile_map.keys())
            
            # Calculate max length for lookahead
            max_name_length = max(len(name) for name in all_targets) if all_targets else 0
            
            # Strip code blocks first to avoid false positives
            # Replace content between backticks with spaces to preserve positions
            content_no_code = re.sub(r'`[^`]*`', lambda m: ' ' * len(m.group(0)), content)
            
            # 1. Find all mentions by scanning character by character
            mentions_found = []
            i = 0
            while i < len(content_no_code):
                if content_no_code[i] == '@':
                    # FIX BUG #9: Check if @ is escaped with backslash
                    # Look back one character to see if it's a backslash
                    if i > 0 and content_no_code[i-1] == '\\':
                        # This @ is escaped, skip it
                        i += 1
                        continue
                    
                    # Look ahead up to max_name_length characters
                    lookahead_end = min(i + 1 + max_name_length, len(content_no_code))
                    lookahead = content_no_code[i+1:lookahead_end]
                    
                    # Find all agent names that match the beginning of lookahead
                    matching_names = []
                    for target in all_targets:
                        if lookahead.startswith(target):
                            matching_names.append(target)
                    
                    # Take the longest match (greedy)
                    if matching_names:
                        longest_match = max(matching_names, key=len)
                        mentions_found.append(longest_match)
                        # Skip past this mention to avoid re-parsing
                        i += len(longest_match) + 1
                        continue
                
                i += 1
            
            # Deduplicate mentions (preserve order of first occurrence)
            seen_mentions = set()
            filtered_mentions = []
            for m in mentions_found:
                if m not in seen_mentions:
                    seen_mentions.add(m)
                    filtered_mentions.append(m)
            
            # 2. Filter / Validate Mentions
            valid_mentions = []
            
            # Get current Queue to check for emptiness later
            queue_raw = state.get("turn", {}).get("queue", [])
            
            for m_name in filtered_mentions:
                # 2a. Resolve Profile Ref -> Agent Name
                target_agent = profile_map.get(m_name, m_name)
                
                # 2b. Permission Check
                # Check if target_agent is allowed.
                # Logic: Is target_agent ID or its Profile in allowed_targets?
                if from_agent != "User":
                    t_info = agents.get(target_agent)
                    t_prof = t_info.get("profile_ref") if t_info else None
                    

                    authorized = False
                    # FIX BUG #6: User mention should also require permission
                    # Check if target is in allowed_targets (by ID or profile)
                    if target_agent in allowed_targets:
                        authorized = True
                    elif t_prof and t_prof in allowed_targets:
                        authorized = True
                    # Special case: "User" might be in allowed_targets as a profile name
                    elif target_agent == "User" and "User" in allowed_targets:
                        authorized = True
                    
                    if not authorized:
                        connections_table = self._build_connections_table(from_agent, state, allowed_targets)
                        return (f"🚫 PERMISSION ERROR: You are not authorized to summon '@{target_agent}' "
                                f"(Profile: {t_prof}). Check your allowed connections."
                                f"\n\n💡 TIP: If you want to reference an agent without mentioning them, "
                                f"use backticks `@{target_agent}` or escape with backslash \\@{target_agent}."
                                f"{connections_table}")
                
                valid_mentions.append(target_agent)

            # --- VISIBILITY CHECKS ---
            if public:
                if "public" not in caps and "public" not in allowed_targets:
                    connections_table = self._build_connections_table(from_agent, state, allowed_targets)
                    return f"🚫 CAPABILITY ERROR: You do not have 'public' capability.{connections_table}"
            else:
                 if "private" not in caps:
                    connections_table = self._build_connections_table(from_agent, state, allowed_targets)
                    return f"🚫 CAPABILITY ERROR: You do not have 'private' capability. Use public=True.{connections_table}"
                     
                 # FIX: Safety Check for Private Messages
                 # If private=True, there MUST be at least one target (Mention or Audience)
                 # Otherwise the message disappears into the void (Bug #13)
                 if not valid_mentions and not audience:
                      connections_table = self._build_connections_table(from_agent, state, allowed_targets)
                      return (f"🚫 VISIBILITY ERROR: You sent a PRIVATE message but mentioned no one. "
                              f"The message would be invisible to everyone.\n"
                              f"You MUST mention the recipient (e.g. @{next(iter(allowed_targets), 'AgentName')}) inside the message."
                              f"{connections_table}")

            # --- QUEUE UPDATE ---
            if not valid_mentions and not queue_raw:
                connections_table = self._build_connections_table(from_agent, state, allowed_targets)
                return ("🚫 TURN ERROR: The queue is empty and you mentioned no one. "
                        "You MUST mention at least one agent (e.g. @User or @AgentName) to pass the turn."
                        f"{connections_table}")

            # Load Queue Objects
            queue_objs = []
            for item in queue_raw:
                if isinstance(item, dict): 
                    queue_objs.append(TurnQueueItem(**item))
                else:
                    queue_objs.append(item)
            
            # Update Logic
            # Fix: Ensure timestamps are strictly increasing to preserve order even if execution is fast
            max_ts = max([i.timestamp for i in queue_objs], default=0.0)
            base_ts = max(time.time(), max_ts + 0.001)
            
            for idx, vm in enumerate(valid_mentions):
                # Check if in queue
                existing = next((i for i in queue_objs if i.name == vm), None)
                if existing:
                    existing.count += 1
                else:
                    queue_objs.append(TurnQueueItem(
                        name=vm, 
                        count=1, 
                        timestamp=base_ts + (idx * 0.001) 
                    ))
            
            # Save back to state
            state["turn"]["queue"] = [i.model_dump() for i in queue_objs]
            
            # --- POST MESSAGE ---
            msg = {
                "from": from_agent,
                "content": content,
                "public": public,
                "target": "Queue", # Virtual target
                "audience": audience or [],
                "mentions": valid_mentions,  # Store mentions for private message filtering
                "timestamp": time.time()
            }
            state.setdefault("messages", []).append(msg)
            
            # Update Logic timestamps
            if from_agent == "User":
                state["turn"]["last_user_message_time"] = time.time()

            # --- TRANSITION ---
            transition_msg = self._finalize_turn_transition(state)
            
            base_msg = f"Message posted. {transition_msg}"
            # Check if self is next
            if state["turn"].get("current") == from_agent:
                 base_msg += "\n[INFO] You retained the turn (you were top of queue)."
            
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
                    "instruction": "SYSTEM RESET: The conversation has been reset by the user. Forget everything. Re-read your Role and Context."
                }
                
            # 1b. Check for Status Reset (Kicked/Reloaded)
            agent_data = data.get("agents", {}).get(agent_name, {})
            my_status = agent_data.get("status")
            if my_status == "pending_connection":
                    return {
                    "status": "reset",
                    "messages": [],
                    "instruction": STOP_INSTRUCTION
                }
            
            # 1c. Check for RELOAD
            if agent_data.get("reload_active"):
                return {
                    "status": "reset",
                    "messages": [],
                    "instruction": RELOAD_INSTRUCTION
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
                    mentions = m.get("mentions", [])  # Get list of mentioned agents
                    
                    if is_public:
                        visible_messages.append(m)
                        continue
                        
                    # Private Logic
                    # A private message is visible if:
                    # 1. I'm the sender
                    # 2. I'm explicitly mentioned in the message
                    # 3. I'm in the audience list
                    # 4. I share the same profile as the sender (team privacy)
                    if sender == agent_name or agent_name in mentions or agent_name in (m.get("audience") or []):
                        visible_messages.append(m)
                    elif my_prof:
                         sender_prof = agents_map.get(sender, {}).get("profile_ref")
                         if sender_prof and sender_prof == my_prof:
                             visible_messages.append(m)
                
                # Build Strategic Advice from Connections
                agents = data.get("agents", {})
                config = data.get("config", {})
                
                backlog_instr = ""
                if config.get("enable_backlog"):
                    backlog_instr = "\n\n⚠️ BACKLOG ENABLED: You must also consult and update the `BACKLOG.md` file at the root of the repo to track tasks and progress."

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
                    "instruction": f"🚨 TURN GRANTED. Read the LATEST CONVERSATION HISTORY above carefully to see what happened while you were waiting.{backlog_instr}{advice_text}"
                }
            
            time.sleep(0.5)  # Reduced from 1s to 0.5s for faster RELOAD detection
            
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
                    "instruction": "SYSTEM RESET: The conversation has been reset by the user. Forget everything. Re-read your Role and Context."
                }
                
            # 1b. Check for Status Reset (Kicked/Reloaded)
            agent_data = data.get("agents", {}).get(agent_name, {})
            my_status = agent_data.get("status")
            if my_status == "pending_connection":
                 return {
                    "status": "reset",
                    "messages": [],
                    "instruction": STOP_INSTRUCTION
                }

            # 1c. Check for RELOAD
            if agent_data.get("reload_active"):
                return {
                    "status": "reset",
                    "messages": [],
                    "instruction": RELOAD_INSTRUCTION
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
                    mentions = m.get("mentions", [])  # Get list of mentioned agents
                    
                    if is_public:
                        visible_messages.append(m)
                        continue
                        
                    # Private Logic
                    # A private message is visible if:
                    # 1. I'm the sender
                    # 2. I'm explicitly mentioned in the message
                    # 3. I'm in the audience list
                    # 4. I share the same profile as the sender (team privacy)
                    if sender == agent_name or agent_name in mentions or agent_name in (m.get("audience") or []):
                        visible_messages.append(m)
                    elif my_prof:
                         sender_prof = agents_map.get(sender, {}).get("profile_ref")
                         if sender_prof and sender_prof == my_prof:
                             visible_messages.append(m)
                
                agents = data.get("agents", {})
                config = data.get("config", {})
                
                backlog_instr = ""
                if config.get("enable_backlog"):
                    backlog_instr = "\n\n⚠️ BACKLOG ENABLED: You must also consult and update the `BACKLOG.md` file at the root of the repo to track tasks and progress."

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
                    "instruction": f"It is your turn. Speak.{backlog_instr}{advice_text}"
                }
            
            await asyncio.sleep(0.5)  # Reduced from 1s to 0.5s for faster RELOAD detection
            
        return {
            "status": "timeout",
            "messages": [],
            "instruction": "Still waiting for turn. connection_timeout_imminent. CALL THIS TOOL AGAIN IMMEDIATELY."
        }
