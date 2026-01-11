from mcp.server.fastmcp import FastMCP
import sys
import os
from typing import List, Optional

# Add src to path to allow imports if run directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

try:
    from src.core.logic import Engine
except ImportError:
    # Fallback for relative imports if installed as package
    from .logic import Engine

# Initialize
mcp = FastMCP("MultiAgent-Hub", dependencies=["portalocker", "streamlit"])
engine = Engine()

# Global state for this process (Stdio session)
# Used as fallback if sending_agent is not provided in talk
SESSION_AGENT_NAME = None

@mcp.tool()
def agent(name: str) -> str:
    """
    INITIALIZATION TOOL. Call this ONCE at the start.
    Bloque jusqu'à ce que tous les agents soient connectés.
    Retourne votre Rôle et le Contexte initial.
    
    Args:
        name: Your unique agent name (e.g. "Architect", "Coder").
    """
    global SESSION_AGENT_NAME
    SESSION_AGENT_NAME = name
    
    print(f"Agent '{name}' connecting...", file=sys.stderr)
    return engine.wait_for_all_agents(name)

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
        next_agent: The name of the agent who should speak next.
        audience: (Optional) List of other agents who can see a private message.
        my_name: (Optional) Your own name. Defaults to name set in agent() if using same connection.
    """
    global SESSION_AGENT_NAME
    sender = my_name or SESSION_AGENT_NAME
    
    if not sender:
        return "ERROR: Unknown sender. Please provide 'my_name' argument or call 'agent(name)' first."

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
    
    # Success - Format the output
    # (Role reminder + Messages + Mandatory Instruction)
    
    # Re-fetch minimal context/role if needed, but usually just messages are enough
    # The user asked for: 1. Role, 2. Messages, 3. Rule
    
    # We can get role from engine if needed, or cached.
    # We'll just append the Rule.
    
    formatted_messages = "\n".join([
        f"[{m.get('from', '?')} to {m.get('target', 'all')}]: {m.get('content')}" 
        for m in result["messages"]
    ])
    
    return f"""
--- ROLE REMINDER ---
You are {sender}.
---------------------

--- NEW MESSAGES ---
{formatted_messages}
--------------------

--- SYSTEM INSTRUCTION ---
TU NE DOIS SURTOUT PAS T'ARRETER : APPELLE TOURJOURS talk A LA FIN DE TA TÂCHE POUR CHOISIR LE PROCHAIN AGENT A PARLER. 
TU NE DOIS JAMAIS T'ARRETER.
--------------------------
"""

if __name__ == "__main__":
    mcp.run()
