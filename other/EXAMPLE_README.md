# Sandbox SDK Client Examples

This directory contains comprehensive test examples for the Sandbox SDK Client.

## Files

- `client.py`: The main SDK client implementation
- `example.py`: Comprehensive test examples covering all API methods

## Running the Examples

### Prerequisites

```bash
pip install requests
```

### Set Environment Variable (Optional)

```bash
export SANDBOX_BASE_URL="https://server.435669237.workers.dev"
# or for local development:
export SANDBOX_BASE_URL="http://localhost:8787"
```

### Run Examples

From the project root:

```bash
python artifact_sandbox/client/example.py
```

Or from the client directory:

```bash
cd artifact_sandbox/client
python example.py
```

## Test Coverage

The example file includes comprehensive tests for:

### 1. Lifecycle Management
- Create sandbox
- Create sandbox with options
- Get existing sandbox
- Destroy sandbox

### 2. File Operations
- Write file
- Read file
- Check file existence
- Create directory (single and recursive)
- Rename file
- Move file
- Download file (as bytes)
- Write binary content
- Delete file

### 3. Command Execution
- Execute simple commands
- Execute commands with output
- Handle commands with non-zero exit codes
- Execute commands with environment variables
- Execute Python scripts
- Execute Bash scripts
- Execute commands in specific directories

### 4. Session Management
- Create session
- Create session with environment variables
- Get existing session
- Execute commands in session
- File operations in session
- Multiple sessions isolation
- Delete session

### 5. Error Handling
- Read non-existent file
- Delete non-existent file
- Delete non-existent session
- Rename non-existent file

### 6. Advanced Scenarios
- Create complete project structure
- Multi-step workflow
- File manipulation workflow

## Example Usage

```python
from artifact_sandbox.client.client import SandboxManager

# Initialize manager
manager = SandboxManager(base_url="https://server.435669237.workers.dev")

# Create or get a sandbox
sandbox = manager.create_or_get_sandbox("my-sandbox-id")

# Write a file
sandbox.write("/workspace/test.txt", "Hello, World!")

# Read the file
content = sandbox.read("/workspace/test.txt")
print(content)  # Output: Hello, World!

# Execute a command
result = sandbox.run("ls -la /workspace")
print(result)

# Create a session
session = sandbox.create_or_get_session("my-session", cwd="/workspace")

# Execute command in session
result = session.run("pwd")

# Clean up
manager.destroy_sandbox("my-sandbox-id")
```

## Notes

- The examples use unique sandbox IDs with timestamps to avoid conflicts
- Some tests intentionally trigger errors to verify error handling
- The script automatically cleans up test sandboxes at the end
- All operations are logged with detailed output

