from pydantic import BaseModel, Field, ConfigDict, ValidationError
from typing import List, Dict, Optional, Any, Union

class BaseSchema(BaseModel):
    model_config = ConfigDict(extra='ignore', populate_by_name=True)

class Connection(BaseSchema):
    target: str
    context: str = ""
    authorized: bool = True

class Profile(BaseSchema):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    public_description: Optional[str] = None
    emoji: str = "🤖"
    system_prompt: Optional[str] = ""
    count: int = 1
    capabilities: List[str] = Field(default_factory=list)
    connections: List[Connection] = Field(default_factory=list)

class Config(BaseSchema):
    total_agents: int = 2
    context: str = ""
    user_availability: str = "available"
    profiles: List[Profile] = Field(default_factory=list)

class AgentState(BaseSchema):
    role: str = ""
    status: str = "connected"
    profile_ref: str
    emoji: str = "🤖"
    connections: Optional[List[Connection]] = None

class Turn(BaseSchema):
    current: Optional[str] = None
    next: Optional[str] = None
    first_agent: Optional[str] = None

class Message(BaseSchema):
    from_: str = Field(..., alias="from")
    content: str
    timestamp: float
    public: bool = False
    target: Optional[str] = None
    audience: List[str] = Field(default_factory=list)

class GlobalState(BaseSchema):
    conversation_id: str
    messages: List[Message] = Field(default_factory=list)
    turn: Turn = Field(default_factory=Turn)
    agents: Dict[str, AgentState] = Field(default_factory=dict)
    config: Config = Field(default_factory=Config)
