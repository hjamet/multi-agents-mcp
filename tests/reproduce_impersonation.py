
import unittest
import sys
import os
import json
import time
import subprocess
import threading

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
SERVER_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "core", "server.py"))

class ServerProcess:
    def __init__(self):
        cmd = ["uv", "run", "python", SERVER_SCRIPT]
        self.state_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "state_repro.json"))
        
        # Initial State: Agent1 connected, Agent1's Turn
        initial_state = {
            "messages": [],
            "conversation_id": "repro-uuid",
            "turn": {"current": "Agent1", "next": None, "queue": []},
            "agents": {
                 "Agent1": {"status": "connected", "role": "Role1", "profile_ref": "Profile1", "connections": []},
                 "Agent2": {"status": "connected", "role": "Role2", "profile_ref": "Profile1", "connections": []}
            },
            "config": {
                "total_agents": 2,
                "profiles": [{"name": "Profile1", "capabilities": ["public", "private", "turn", "open"]}]
            }
        }
        with open(self.state_file, "w") as f:
            json.dump(initial_state, f)
            
        env = os.environ.copy()
        env["MULTI_AGENT_STATE_PATH"] = self.state_file
        
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env
        )
        self.responses = {}
        self.stdout_thread = threading.Thread(target=self._reader, daemon=True)
        self.stdout_thread.start()
        self.stderr_thread = threading.Thread(target=self._stderr_reader, daemon=True)
        self.stderr_thread.start()

    def _reader(self):
        while True:
            line = self.process.stdout.readline()
            if not line: break
            print(f"[RAW] {line.strip()}", file=sys.stderr) # Valid debugging
            try:
                data = json.loads(line)
                if "id" in data:
                    self.responses[data["id"]] = data
            except Exception as e:
                print(f"[JSON ERROR] {e} | Line: {line[:50]}...", file=sys.stderr)

    def _stderr_reader(self):
        for line in self.process.stderr:
            print(f"[SERVER ERR] {line}", end='')

    def call_tool(self, name, args, timeout=5):
        rid = int(time.time() * 1000)
        req = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
            "id": rid
        }
        self.process.stdin.write(json.dumps(req) + "\n")
        self.process.stdin.flush()
        
        start = time.time()
        while time.time() - start < timeout:
            if rid in self.responses:
                res = self.responses[rid]
                if "result" in res:
                    return res["result"]["content"][0]["text"]
                if "error" in res:
                    raise RuntimeError(res["error"])
            time.sleep(0.1)
        raise TimeoutError("Tool call timed out")

    def terminate(self):
        self.process.terminate()
        self.process.wait()

class TestImpersonation(unittest.TestCase):
    def test_impersonation_deadlock(self):
        server = ServerProcess()
        try:
            # Initialize
            rid = 1
            req = {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}, "id": rid}
            server.process.stdin.write(json.dumps(req) + "\n")
            server.process.stdin.flush()
            time.sleep(1) # wait for init

            print("Attempting validation...")
            # Agent1 (Turn Holder) calls talk but pretends to be Agent2
            # CURRENTLY: This blocks (TimeoutError)
            # DESIRED: This returns Error immediately
            
            start = time.time()
            try:
                # We expect a Fast Timeout if it blocks, or Immediate Error if fixed
                result = server.call_tool("talk", {
                    "message": "I am Agent2",
                    "from_agent": "Agent2",  # IMPERSONATION! Turn is Agent1
                    "public": True
                }, timeout=3)
                
                print(f"Result: {result}")
                
                # If we are here, it didn't block.
                # Check for Error Message
                if "SECURITY VIOLATION" in result or "Identity" in result:
                    print("PASS: Got Security Error")
                else: 
                     print("FAIL: Got success or unrelated message")

            except TimeoutError:
                print("FAIL: Deadlock detected (Client timed out waiting for tool)")
            
        finally:
            server.terminate()

if __name__ == "__main__":
    unittest.main()
