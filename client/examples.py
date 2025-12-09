"""
Usage examples demonstrating Sandbox and ExecutionSession.

Before running, ensure:
1. Environment variable SANDBOX_BASE_URL is set (default: http://localhost:8787)
2. Environment variable SANDBOX_ID is set (obtained when the server starts)
3. The server is running (npm run dev)
"""

import os
import sys
from pathlib import Path

# Add current directory to sys.path to import client module
sys.path.insert(0, str(Path(__file__).parent))

from client import Sandbox, SandboxManager, SandboxError


def example_basic_usage(manager: SandboxManager, sandbox_id: str):
    """Example 1: Basic usage with the default session"""
    print("\n=== Example 1: Basic Usage ===")
    
    sandbox = manager.create_or_get_sandbox(sandbox_id)

    # Write a file
    sandbox.write("/workspace/hello.txt", "Hello, Sandbox!")
    print("✓ File written")

    # Read the file
    content = sandbox.read("/workspace/hello.txt")
    print(f"✓ File content: {content}")

    # Run a command
    result = sandbox.run("cat /workspace/hello.txt")
    print(f"✓ Command output: {result.get('stdout', '').strip()}")

    # Clean up
    sandbox.delete("/workspace/hello.txt")
    print("✓ File deleted")

    manager.destroy_sandbox(sandbox.sandbox_id)


def example_sessions(manager: SandboxManager, sandbox_id: str):
    """Example 2: Multiple isolated sessions"""
    print("\n=== Example 2: Multiple Sessions ===")

    # Ensure we use a clean sandbox

    sandbox = manager.create_or_get_sandbox(sandbox_id)


    # Create two isolated sessions
    prod_session = sandbox.create_or_get_session(
        session_id="prod",
        env={"NODE_ENV": "production"},
        cwd="/workspace/prod",
    )
    test_session = sandbox.create_or_get_session(
        session_id="test",
        env={"NODE_ENV": "test"},
        cwd="/workspace/test",
    )
    prod_dir = "/workspace/prod"
    if not test_session.exists(prod_dir):#TODO: all sessions share the container filesystem
        # Create directory if missing to avoid mkdir errors on reruns
        sandbox.mkdir(prod_dir, recursive=True)
        print("✓ Directory created")
    else:
        print("✓ Directory already exists, skip creation")

    # Write a sample config file for the prod session
    prod_session.write(f"{prod_dir}/config.json", '{"env": "production"}')
    # manager.destroy_all_sandboxes()
    #
    # # Set different env vars in each session
    # prod_session.mkdir("/workspace/prod")
    # test_session.mkdir("/workspace/test")
    # prod_session.write("/workspace/prod/config.json", '{"env": "production"}')
    # test_session.write("/workspace/test/config.json", '{"env": "test"}')
    #
    # # Verify isolation (use absolute paths to avoid cwd issues)
    prod_result = prod_session.run("cat /workspace/prod/config.json")
    # test_result = test_session.run("cat /workspace/test/config.json")
    print(f"✓ Prod session config: {prod_result.get('stdout') } and { prod_result.get('output')}")
    # print(f"✓ Test session config: {test_result.get('stdout') or test_result.get('output')}")
    #
    # # Cleanup
    sandbox.delete_session("prod")
    # manager.destroy_all_sandboxes()
    # sandbox.delete_session("test")


def example_session_persistence(manager: SandboxManager, sandbox_id: str):
    """Example 3: Session state persistence"""
    print("\n=== Example 3: Session Persistence ===")
    
    sandbox = manager.create_or_get_sandbox(sandbox_id)
    
    # Create a session and (optionally) set working directory
    session = sandbox.create_or_get_session(
        session_id="my-task2",
        #TODO: investigate why create session path differs when auto-created with get session
        #cwd="/workspace/my-project"
    )
    print("Current working directory")
    print(session.run("pwd"))

    print("Command logs")
    # Run multiple commands; state (cwd/env/process) is preserved
    print(session.run("mkdir -p src"))
    print(session.run("cd src && echo 'console.log(\"Hello\");' > app.js"))

    print("Current working directory")
    result = session.run("pwd")
    print(f"✓ Current dir: {result}")

    result = session.run("ls -la src/")
    print(f"✓ File list:\n{result}")

    # Restore session (simulate reconnect)
    restored_session = sandbox.create_or_get_session("my-task")
    result = restored_session.run("pwd")
    print(f"✓ Restored dir: {result}")

    # Cleanup

    # print("✓ Session cleaned")


def example_file_operations(manager: SandboxManager, sandbox_id: str):
    """Example 4: File operations"""
    print("\n=== Example 4: File Operations ===")
    
    sandbox = manager.create_or_get_sandbox(sandbox_id)
    session = sandbox.create_or_get_session("file-demo")
    
    # Create directory
    sandbox.mkdir("/workspace/files", recursive=True)
    
    # Write file
    session.write("/workspace/files/data.txt", "123456")
    print("✓ File written")
    
    # Read file
    content = session.read("/workspace/files/data.txt")
    print(f"✓ File content: {content}")
    
    # Check existence
    exists = sandbox.exists("/workspace/files/data.txt")
    print(f"✓ File exists: {exists}")

    # Rename
    sandbox.rename("/workspace/files/data.txt", "/workspace/files/renamed.txt")
    print("✓ File renamed")

    # Move
    sandbox.move("/workspace/files/renamed.txt", "/workspace/moved.txt")
    print("✓ File moved to /workspace/moved.txt")
    
    # List directory (via command)
    ls_result = session.run("ls -l /workspace")
    print(f"✓ Directory contents:\n{ls_result}")
    
    # Download file (as bytes)
    file_bytes = session.download("/workspace/moved.txt")
    print(f"✓ File size: {len(file_bytes)} bytes")
    with open("save.txt",'wb') as f:
        f.write(file_bytes)
    
    # Delete file
    session.delete("/workspace/moved.txt")
    print("✓ File deleted")
    
    sandbox.delete_session("file-demo")


def example_script_execution(manager: SandboxManager, sandbox_id: str):
    """Example 5: Execute a script file"""
    print("\n=== Example 5: Execute Script ===")
    
    sandbox = manager.create_or_get_sandbox(sandbox_id)
    session = sandbox.create_or_get_session("script-demo")

    # Execute script
    result = session.run_script(
        "./test_py.py",
        interpreter="python3",
    )
    print("✓ Script execution result:")
    print(result)
    sandbox.delete_session("script-demo")


def example_error_handling(manager: SandboxManager, sandbox_id: str):
    """Example 6: Error handling"""
    print("\n=== Example 6: Error Handling ===")
    
    sandbox = manager.create_or_get_sandbox(sandbox_id)
    
    try:
        # Try reading a non-existent file
        sandbox.read("/workspace/nonexistent.txt")
    except SandboxError as e:
        print(f"✓ Caught error: {e}")
        print(f"  Status: {e.status_code}")
    
    try:
        # Try deleting a missing session
        sandbox.delete_session("nonexistent")
    except SandboxError as e:
        print(f"✓ Caught error: {e}")
    
    try:
        # Try deleting default session (not allowed)
        sandbox.delete_session("default")
    except SandboxError as e:
        print(f"✓ Caught error: {e}")


def example_bucket_mount(manager: SandboxManager, sandbox_id: str):
    """Example 8: Bucket mount (R2/S3 compatible, production)"""
    print("\n=== Example 8: Bucket Mount ===")
    sandbox = manager.create_or_get_sandbox(sandbox_id)

    # Prepare config (requires production; wrangler dev does not support FUSE)
    bucket = os.environ.get("SANDBOX_BUCKET", "my-bucket")
    endpoint = os.environ.get("SANDBOX_BUCKET_ENDPOINT", "")
    access_key = os.environ.get("SANDBOX_BUCKET_ACCESS_KEY")
    secret_key = os.environ.get("SANDBOX_BUCKET_SECRET_KEY")

    if not endpoint:
        print("⚠️ Skip: please set SANDBOX_BUCKET_ENDPOINT to test mount")
        return

    options: dict = {"endpoint": endpoint}
    if access_key and secret_key:
        options["credentials"] = {"accessKeyId": access_key, "secretAccessKey": secret_key}

    # Mount in the default session
    mount_path = "/data"
    result = sandbox.mount_bucket(bucket, mount_path, options)
    print(f"✓ Mounted in default session: {result}")

    # Mount in a specific session and access it
    session = sandbox.create_or_get_session("storage-demo")
    session.mount_bucket(bucket, mount_path, options)
    ls_result = session.run("ls -l /data")
    print("✓ List mounted directory:\n", ls_result.get("output", ""))

    # Unmount
    session.unmount_bucket(mount_path)
    sandbox.unmount_bucket(mount_path)
    sandbox.delete_session("storage-demo")
    print("✓ Mount/unmount flow complete")


def main():
    """Run all examples"""
    print("=" * 60)
    print("Sandbox SDK Examples")
    print("=" * 60)

    # Read environment variables
    sandbox_id = os.environ.get("SANDBOX_ID", "your-sandbox-id")
    base_url = os.environ.get("SANDBOX_BASE_URL")


    # Create SandboxManager instance
    manager = SandboxManager(base_url=base_url) if base_url else SandboxManager()
    
    try:
        example_basic_usage(manager, sandbox_id)
        # example_sessions(manager, sandbox_id)
        # example_session_persistence(manager, sandbox_id)
        # example_file_operations(manager, sandbox_id)
        # example_script_execution(manager, sandbox_id)
        # example_error_handling(manager, sandbox_id)
        # example_bucket_mount(manager, sandbox_id)
        
    except SandboxError as e:
        print(f"\n❌ Sandbox error: {e}")
        if e.status_code:
            print(f"   Status: {e.status_code}")
        if e.response_text:
            print(f"   Response: {e.response_text}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

