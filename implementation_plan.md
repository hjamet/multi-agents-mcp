# Hardening Content Files with Read-Only Permissions

## Goal Description
Prevent agents from modifying `MEMORY.md` and `CONVERSATION.md` by applying read-only permissions (`0o444`) immediately after the system writes to them. This enforces the "Source of Truth" rule.

## User Review Required
> [!IMPORTANT]
> This change will cause `PermissionError` if an agent attempts to write to these files using standard file I/O tools. This is the intended behavior.

## Proposed Changes

### Core Server
#### [MODIFY] [server.py](file:///home/lopilo/code/multi-agents-mcp/src/core/server.py)
- Import `stat` (optional, using octal `0o444` is sufficient and cleaner).
- In `_write_context_files`:
    - After writing `MEMORY.md`, apply `os.chmod(mem_path, 0o444)`.
    - After writing `CONVERSATION.md`, apply `os.chmod(conv_path, 0o444)`.

## Verification Plan
### Automated Tests
- This is a system-level change. We rely on the system loop.
- **Atlas (DevOps)** will attempt to write to `MEMORY.md` using `write_to_file`.
- Expected Result: The tool call should fail with a `PermissionError`.

### Manual Verification
- Verify that `MEMORY.md` and `CONVERSATION.md` have `r--r--r--` permissions (444) in the filesystem.
