from mcp.server.fastmcp import FastMCP
import time
import sys

# Initialize FastMCP server
mcp = FastMCP("MultiAgent-TimeoutTest")

@mcp.tool()
def wait(seconds: int) -> str:
    """
    Waits for a specified number of seconds to test timeout limits.
    Use this to verify if the MCP connection stays alive during long delays.
    """
    print(f"Starting wait of {seconds} seconds...", file=sys.stderr)
    start_time = time.time()
    time.sleep(seconds)
    end_time = time.time()
    duration = end_time - start_time
    print(f"Finished wait. Actual duration: {duration:.2f}s", file=sys.stderr)
    
    return f"Successfully waited {seconds} seconds. (Actual: {duration:.2f}s)"

if __name__ == "__main__":
    mcp.run()
