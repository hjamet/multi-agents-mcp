import time
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

    def register_agent(self, name: str) -> Dict[str, Any]:
        """
        Registers an agent as 'connected'.
        Returns a dict containing context if ready, or status.
        """
        def _register(state):
            agents = state.setdefault("agents", {})
            config = state.setdefault("config", {"total_agents": 2}) # Default if missing
            
            # Update status
            if name not in agents:
                # Assign default role if new (simple version)
                # Ideally roles are pre-seeded in config page
                role = "Participant"
                agents[name] = {"role": role, "status": "connected"}
            else:
                agents[name]["status"] = "connected"
                
            # Check if all connected
            connected_count = sum(1 for a in agents.values() if a.get("status") == "connected")
            total_required = config.get("total_agents", 2)
            
            ready = connected_count >= total_required
            
            return {
                "role": agents[name]["role"],
                "ready": ready,
                "connected_count": connected_count,
                "total_required": total_required,
                "other_agents": [n for n in agents if n != name]
            }

        return self.state.update(_register)

    def wait_for_all_agents(self, name: str, timeout_seconds: int = 600) -> str:
        """
        Blocks until all agents are connected.
        Returns the System Context string.
        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            # Poll status
            info = self.register_agent(name) # Keepalive / check
            
            if info["ready"]:
                # Build context
                context = config.get("context", "")
                other_agents = ", ".join(info["other_agents"])
                return (
                    f"CONTEXT: {context}\n\n"
                    f"You are {name}. Role: {info['role']}.\n"
                    f"Network is READY. Connected agents: {len(info['other_agents']) + 1}/{info['total_required']}.\n"
                    f"Peers: {other_agents}.\n"
                    "You may now speak if it is your turn."
                )
            
            time.sleep(2) # Polling interval
        
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
            
            sender_info = agents.get(from_agent, {})
            sender_profile_name = sender_info.get("profile_ref")
            
            # Find Sender Profile
            sender_profile = next((p for p in profiles if p["name"] == sender_profile_name), None)
            
            if not sender_profile:
                # Fallback: If no profile found (e.g. manual/legacy), we block unless strictness is off?
                # User asked for strict enforcement.
                # However, let's allow if the system is bootstrapping (e.g. Role assignment phase? No, talk is later).
                # Let's BLOCK unknown agents to force proper config.
                return f"🚫 ACTION DENIED: Agent '{from_agent}' has no valid profile configuration. Please ask Admin to configure you in the Cockpit."

            caps = sender_profile.get("capabilities", [])
            connections = sender_profile.get("connections", [])
            allowed_targets = {c["target"]: c["context"] for c in connections} # Profile Names
            
            # A. Capability Checks
            if public and "public" not in caps:
                return f"🚫 ACTION DENIED: You do not have the 'public' capability. You must send a Private message to a specific target."
            
            if not public and "private" not in caps:
                 return f"🚫 ACTION DENIED: You do not have the 'private' capability. You must speak Publicly."
            
            if audience and "audience" not in caps:
                 return f"🚫 ACTION DENIED: You do not have the 'audience' capability. You cannot cc additional agents."
            
            # B. Connection Checks (Skip if OPEN)
            if "open" not in caps:
                # Helper to check one target
                def check_target(t_name):
                    # target instance name (e.g. Wolf_1) -> profile (Wolf)
                    t_info = agents.get(t_name)
                    if not t_info:
                        return f"Unknown agent '{t_name}'"
                    t_prof = t_info.get("profile_ref")
                    if t_prof not in allowed_targets:
                         return f"Not connected to '{t_prof}'"
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
            state["turn"]["current"] = next_agent
            state["turn"]["next"] = None # Consumed
            
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
                
                # Filter messages for this agent
                # Visible = Public OR (Private AND (To Me OR From Me OR In Audience))
                visible_messages = []
                for m in messages:
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
                            target = conn.get("target")
                            ctx = conn.get("context")
                            advice_text += f"- If talking to {target}: {ctx}\n"
                        advice_text += "------------------------"

                return {
                    "status": "success",
                    "messages": visible_messages[-10:], # Return last 10 relevant messages
                    "instruction": f"It is your turn. Speak.{advice_text}"
                }
            
            time.sleep(1)
            
        return {
            "status": "timeout",
            "messages": [],
            "instruction": "Still waiting for turn. connection_timeout_imminent. CALL THIS TOOL AGAIN IMMEDIATELY."
        }
