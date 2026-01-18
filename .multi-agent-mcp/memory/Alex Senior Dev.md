Action: Implemented `history` tool in `server.py`.
Logic: Retrieves N-th message from author + context [-1, +1]. Formatted as XML.
Dependencies: Uses `_format_conversation_history` (with agent=None) and `_truncate_and_buffer`.
Next: Miller to verify/reload.