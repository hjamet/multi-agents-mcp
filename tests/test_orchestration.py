import pytest
import subprocess
import sys
import os
import json
import time
import threading
from typing import Dict, Any, Optional

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

SERVER_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "core", "server.py"))

class ServerProcess:
    def send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        req = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
            # No ID for notifications
        }
        
        json_req = json.dumps(req)
        try:
            self.process.stdin.write(json_req + "\n")
            self.process.stdin.flush()
        except BrokenPipeError:
            raise RuntimeError("Server process died unexpectedly.")

    def send_request_async(self, method: str, params: Optional[Dict[str, Any]] = None) -> int:
        """Sends a request and returns the ID, does not wait for response."""
        with self.lock:
            self.request_id += 1
            curr_id = self.request_id
        
        req = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": curr_id
        }
        
        json_req = json.dumps(req)
        try:
            self.process.stdin.write(json_req + "\n")
            self.process.stdin.flush()
        except BrokenPipeError:
            raise RuntimeError("Server process died unexpectedly.")
            
        return curr_id

    def read_response(self, request_id: int, timeout=5) -> Any:
        # Simple blocking read loop that discards others until match
        start = time.time()
        while time.time() - start < timeout:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("Server closed connection.")
            
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
                
            if data.get("id") == request_id:
                if "error" in data:
                    raise RuntimeError(f"RPC Error: {data['error']}")
                return data["result"]
            # Buffer others? For this simple test we might lose them if we don't buffer.
             # Ideally we should have a background reader thread filling a dict of futures.
        raise TimeoutError(f"Timeout waiting for request {request_id}")

    # Advanced Client with buffering
    def __init__(self, use_single_agent=False):
        # Use uv run to ensure dependencies are available in the subprocess
        cmd = ["uv", "run", "python", SERVER_SCRIPT]
        
        # Use a temporary state file for testing
        suffix = "_single" if use_single_agent else "_multi"
        self.state_file = os.path.abspath(os.path.join(os.path.dirname(__file__), f"state_test{suffix}.json"))
        
        # Pre-populate state file
        if use_single_agent:
             initial_state = {
                "messages": [],
                "conversation_id": "test-uuid-single",
                "turn": {"current": "Agent1", "next": None},
                "agents": {
                     "Agent1": {"status": "pending_connection", "role": "Test Role 1"}
                },
                "config": {"total_agents": 1}
            }
        else:
            initial_state = {
                "messages": [],
                "conversation_id": "test-uuid-multi",
                "turn": {"current": "Agent1", "next": None},
                "agents": {
                     "Agent1": {"status": "pending_connection", "role": "Test Role 1"},
                     "Agent2": {"status": "pending_connection", "role": "Test Role 2"}
                },
                "config": {"total_agents": 2}
            }

        with open(self.state_file, "w") as f:
            json.dump(initial_state, f)
            
        env = os.environ.copy()
        env["MULTI_AGENT_STATE_PATH"] = self.state_file
        
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, # Capture stderr to assert Warnings
            text=True,
            bufsize=1, # Line buffered
            env=env
        )
        self.lock = threading.Lock()
        self.request_id = 0
        self.responses = {}
        self.stderr_log = []
        
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()
        
        self.stderr_thread = threading.Thread(target=self._stderr_loop, daemon=True)
        self.stderr_thread.start()

    def _reader_loop(self):
        while True:
            line = self.process.stdout.readline()
            if not line:
                break
            try:
                data = json.loads(line)
                if "id" in data:
                    self.responses[data["id"]] = data
            except:
                pass
                
    def _stderr_loop(self):
        # Read stderr line by line
        for line in self.process.stderr:
            self.stderr_log.append(line.strip())
            # print(f"[SERVER STDERR] {line.strip()}", file=sys.stderr)

    def get_response(self, request_id: int, timeout=10) -> Any:
        start = time.time()
        while time.time() - start < timeout:
            if request_id in self.responses:
                data = self.responses[request_id]
                if "error" in data:
                     raise RuntimeError(f"RPC Error: {data['error']}")
                return data["result"]
            time.sleep(0.1)
        raise TimeoutError(f"Timeout waiting for request {request_id}")

    def call_tool(self, name: str, arguments: Dict[str, Any] = {}) -> Any:
        # Blocking call
        rid = self.send_request_async("tools/call", {"name": name, "arguments": arguments})
        res = self.get_response(rid)
        return res.get("content", [{}])[0].get("text", "")
    
    def call_tool_async(self, name: str, arguments: Dict[str, Any] = {}) -> int:
        return self.send_request_async("tools/call", {"name": name, "arguments": arguments})
        
    def get_tool_result(self, request_id: int) -> str:
        res = self.get_response(request_id)
        return res.get("content", [{}])[0].get("text", "")

    def terminate(self):
        self.process.terminate()
        self.process.wait()

@pytest.fixture
def server_multi():
    proc = ServerProcess(use_single_agent=False)
    proc.send_request_async("initialize", {
        "protocolVersion": "2024-11-05", 
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0"}
    })
    rid = proc.request_id 
    proc.get_response(rid)
    proc.send_notification("notifications/initialized")
    yield proc
    proc.terminate()

@pytest.fixture
def server_single():
    proc = ServerProcess(use_single_agent=True)
    proc.send_request_async("initialize", {
        "protocolVersion": "2024-11-05", 
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0"}
    })
    rid = proc.request_id 
    proc.get_response(rid)
    proc.send_notification("notifications/initialized")
    yield proc
    proc.terminate()

def test_session_collision(server_multi):
    """
    Simulates collision.
    """
    # 1. Register A1
    rid1 = server_multi.call_tool_async("agent", {})
    # 2. Register A2 (Collision!)
    rid2 = server_multi.call_tool_async("agent", {})
    
    res1 = server_multi.get_tool_result(rid1)
    res2 = server_multi.get_tool_result(rid2)
    
    assert "REGISTRATION SUCCESSFUL" in res1
    assert "REGISTRATION SUCCESSFUL" in res2
    
    # Assert Warning in Stderr
    time.sleep(1) # Wait for log flush
    log_content = "\n".join(server_multi.stderr_log)
    assert "SESSION WARNING" in log_content
    print("Verified Session Collision Warning.")

def test_features_single_agent(server_single):
    """
    Verifies History, Memory using single agent.
    """
    # 1. Register A1
    resp = server_single.call_tool("agent", {})
    assert "REGISTRATION SUCCESSFUL" in resp
    
    # 2. Note (Memory)
    server_single.call_tool("note", {"content": "My Secret Note"})
    
    # 3. Talk (Send Public Message) -> Triggers new Turn Prompt
    # Since turn is A1, and we speak, turn loops back to A1 (since only 1 agent) or gets stuck?
    # Logic: next_agent=A1.
    res_talk = server_single.call_tool("talk", {"message": "Hello World", "public": True, "to": "Agent1"})
    assert "Next speaker is Agent1" in res_talk
    
    # 4. Turn Loop
    # Now that we spoke, the server passes turn to A1.
    # But `talk` tool blocks until turn comes back!
    # Since we sent to A1, it comes back immediately.
    # So `call_tool("talk")` should return with the NEW prompt.
    # WAIT. `talk` returns STRING "Message posted...". 
    # It sends Turn Change.
    # Then it waits for turn in `wait_for_turn`.
    # Then renders `talk_response.j2`.
    
    # If `res_talk` is the TEMPLATE, then it confirms full loop!
    # Check content of `res_talk`.
    
    assert "Hello World" in res_talk # Check message history visibility
    assert "My Secret Note" in res_talk # Check Memory visibility
    
    print("Verified History and Memory.")
