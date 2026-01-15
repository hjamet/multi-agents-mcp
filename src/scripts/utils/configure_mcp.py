import json
import os
import sys
import argparse
from pathlib import Path

def configure_mcp(name, project_path, is_dev=False):
    """
    Configures MCP for Gemini Antigravity, Cursor IDE, and Gemini CLI.
    """
    project_path = os.path.abspath(project_path)
    server_script = os.path.join(project_path, 'src', 'core', 'server.py')
    
    if not os.path.exists(server_script):
        print(f"Error: Server script not found at {server_script}")
        sys.exit(1)

    # Command to run the MCP server
    # We use 'sh -c' to ensure we can 'cd' and 'uv run' properly
    command_str = f'cd {project_path} && uv run python {server_script}'
    
    server_config = {
        'command': 'sh',
        'args': ['-c', command_str],
        'env': {}
    }

    # Paths to configure
    configs = [
        os.path.expanduser('~/.gemini/antigravity/mcp_config.json'),
        os.path.expanduser('~/.cursor/mcp.json'),
        os.path.expanduser('~/.gemini/settings.json')
    ]

    for config_path in configs:
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        print(f"Warning: {config_path} is invalid JSON. Overwriting.")
                        data = {"mcpServers": {}}
            else:
                data = {"mcpServers": {}}

            if 'mcpServers' not in data:
                data['mcpServers'] = {}

            # Add/Update the server
            data['mcpServers'][name] = server_config
            
            # If it's the main server, maybe remove the dev one to clean up? 
            # Or vice-versa? No, let's keep them separate as requested.

            with open(config_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"✅ Updated {config_path}")

        except Exception as e:
            print(f"❌ Failed to update {config_path}: {e}")
            # We don't exit here to try the next config, but we'll exit at the end if any failed?
            # User rule: Fail-Fast. Let's fail if we can't write a config we expected to be able to.
            sys.exit(1)
    
    # Inform about Gemini CLI if not found
    import shutil
    if not shutil.which('gemini'):
        print("\n💡 Tip: Gemini CLI not found. To use it with this MCP, install it with:")
        print("   npm install -g @google/gemini-cli")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Configure MCP for IDEs')
    parser.add_argument('--name', required=True, help='Name of the MCP server')
    parser.add_argument('--path', required=True, help='Path to the project root')
    parser.add_argument('--dev', action='store_true', help='Is this a development installation')
    
    args = parser.parse_args()
    configure_mcp(args.name, args.path, args.dev)
