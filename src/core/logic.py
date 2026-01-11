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
                other_agents = ", ".join(info["other_agents"])
                return (
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
        """
        def _post(state):
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
        Returns dict with keys: 'status' (success/timeout), 'messages' (list), 'instructions' (str).
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            try:
                data = self.state.load()
            except Exception:
                time.sleep(1)
                continue
                
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
                
                return {
                    "status": "success",
                    "messages": visible_messages[-10:], # Return last 10 relevant messages
                    "instruction": "It is your turn. Speak."
                }
                
                # Return raw messages for now, filter in server or here if schema updated.
                return {
                    "status": "success",
                    "messages": messages[-10:], # Return last 10 for context
                    "instruction": "It is your turn. Speak."
                }
            
            time.sleep(1)
            
        return {
            "status": "timeout",
            "messages": [],
            "instruction": "Still waiting for turn. connection_timeout_imminent. CALL THIS TOOL AGAIN IMMEDIATELY."
        }
