#!/usr/bin/env python3
"""
Comprehensive test examples for the Sandbox SDK Client.

This file demonstrates all available API methods and provides test cases
for the Cloudflare Sandbox server.

Usage:
    python example.py
"""

import os
import sys
import time
from typing import Dict, Any

# Add parent directory to path to import client
# This allows running the script from different directories
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(parent_dir)
sys.path.insert(0, project_root)

try:
    from artifact_sandbox.client.client import SandboxManager, SandboxError, Sandbox
except ImportError:
    # Fallback: try importing directly if running from client directory
    from client import SandboxManager, SandboxError


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_test(name: str):
    """Print a test name."""
    print(f"\n[TEST] {name}")
    print("-" * 80)


def print_result(result: Any, label: str = "Result"):
    """Print a formatted result."""
    print(f"\n{label}:")
    if isinstance(result, dict):
        for key, value in result.items():
            if isinstance(value, (str, bytes)) and len(str(value)) > 200:
                print(f"  {key}: {str(value)[:200]}... (truncated)")
            else:
                print(f"  {key}: {value}")
    else:
        print(f"  {result}")


def test_lifecycle_management(manager: SandboxManager):
    """Test sandbox lifecycle operations."""
    print_section("1. Lifecycle Management Tests")
    
    #test_id = f"test-sandbox-{int(time.time())}"
    test_id="123"

    # Test 1.1: Create a new sandbox
    print_test("1.1 Create Sandbox")
    try:
        sandbox = manager.create_or_get_sandbox(test_id)
        print(f"✓ Sandbox created: {test_id}")
        print_result({"sandbox_id": sandbox.sandbox_id})
    except SandboxError as e:
        print(f"✗ Failed to create sandbox: {e}")
        return None
    #
    # # Test 1.2: Create sandbox with options
    # print_test("1.2 Create Sandbox with Options")
    # test_id_with_options = f"test-sandbox-options"
    # try:
    #     options = {#自动销毁的时间 30s后销毁 启用keepalive不会自动销毁
    #         "keepAlive": False,
    #         "sleepAfter": "30s"
    #     }
    #     sandbox2 = manager.create_or_get_sandbox(test_id_with_options, options=options)
    #     print(f"✓ Sandbox created with options: {test_id_with_options}")
    #     print_result({"sandbox_id": sandbox2.sandbox_id, "options": options})
    # except SandboxError as e:
    #     print(f"✗ Failed to create sandbox with options: {e}")
    #
    # # Test 1.3: Get existing sandbox (should not fail)
    # print_test("1.3 Get Existing Sandbox")
    # try:
    #     existing_sandbox = manager.create_or_get_sandbox(test_id)
    #     print(f"✓ Retrieved existing sandbox: {test_id}")
    #     assert existing_sandbox.sandbox_id == test_id
    # except SandboxError as e:
    #     print(f"✗ Failed to get existing sandbox: {e}")
    #
    # # Test 1.4: Destroy sandbox
    # print_test("1.4 Destroy Sandbox")
    # try:
    #     manager.destroy_sandbox(test_id_with_options)
    #     print(f"✓ Sandbox destroyed: {test_id_with_options}")
    # except SandboxError as e:
    #     print(f"✗ Failed to destroy sandbox: {e}")

    return sandbox


def test_file_operations(sandbox: Sandbox):
    """Test file operations."""
    print_section("2. File Operations Tests")
    
    # Test 2.1: Write a file
    print_test("2.1 Write File")
    test_file = "/workspace/test_file.txt"
    test_content = "Hello, World!\nThis is a test file.\nLine 3"
    try:
        sandbox.write(test_file, test_content)
        print(f"✓ File written: {test_file}")
    except SandboxError as e:
        print(f"✗ Failed to write file: {e}")
        return
    
    # Test 2.2: Read a file
    print_test("2.2 Read File")
    try:
        content = sandbox.read(test_file)
        print(f"✓ File read: {test_file}")
        print_result({"content": content}, "File Content")
        assert content == test_content, "Content mismatch!"
    except SandboxError as e:
        print(f"✗ Failed to read file: {e}")

    
    # Test 2.3: Check if file exists
    print_test("2.3 Check File Exists")
    try:
        exists = sandbox.exists(test_file)
        print(f"✓ File exists check: {exists}")
        assert exists == True, "File should exist!"
    except SandboxError as e:
        print(f"✗ Failed to check file existence: {e}")
    
    # Test 2.4: Check if non-existent file exists
    print_test("2.4 Check Non-existent File")
    try:
        exists = sandbox.exists("/workspace/non_existent.txt")
        print(f"✓ Non-existent file check: {exists}")
        assert exists == False, "File should not exist!"
    except SandboxError as e:
        print(f"✗ Failed to check non-existent file: {e}")
    
    # Test 2.5: Create directory
    print_test("2.5 Create Directory")
    test_dir = "/workspace/test_dir"
    try:
        result = sandbox.mkdir(test_dir)
        print(f"✓ Directory created: {test_dir}")
        print_result(result)
    except SandboxError as e:
        print(f"✗ Failed to create directory: {e}")
    
    # Test 2.6: Create nested directories (recursive)
    print_test("2.6 Create Nested Directories (Recursive)")
    nested_dir = "/workspace/nested/deep/structure"
    try:
        result = sandbox.mkdir(nested_dir, recursive=True)
        print(f"✓ Nested directories created: {nested_dir}")
        print_result(result)
    except SandboxError as e:
        print(f"✗ Failed to create nested directories: {e}")
    
    # Test 2.7: Write file to nested directory
    print_test("2.7 Write File to Nested Directory")
    nested_file = f"{nested_dir}/nested_file.txt"
    try:
        sandbox.write(nested_file, "Content in nested directory")
        print(f"✓ File written to nested directory: {nested_file}")
    except SandboxError as e:
        print(f"✗ Failed to write to nested directory: {e}")
    
    # Test 2.8: Rename a file
    print_test("2.8 Rename File")
    new_name = "/workspace/renamed_file.txt"
    try:
        result = sandbox.rename(test_file, new_name)
        print(f"✓ File renamed: {test_file} -> {new_name}")
        print_result(result)
        # Verify rename worked
        assert sandbox.exists(new_name), "Renamed file should exist!"
        assert not sandbox.exists(test_file), "Old file should not exist!"
    except SandboxError as e:
        print(f"✗ Failed to rename file: {e}")
    
    # Test 2.9: Move a file
    print_test("2.9 Move File")
    moved_file = f"{test_dir}/moved_file.txt"
    try:
        result = sandbox.move(new_name, moved_file)
        print(f"✓ File moved: {new_name} -> {moved_file}")
        print_result(result)
        # Verify move worked
        assert sandbox.exists(moved_file), "Moved file should exist!"
        assert not sandbox.exists(new_name), "Original file should not exist!"
    except SandboxError as e:
        print(f"✗ Failed to move file: {e}")
    
    # Test 2.10: Download file (as bytes)
    print_test("2.10 Download File as Bytes")
    try:
        file_bytes = sandbox.download(moved_file)
        print(f"✓ File downloaded: {moved_file}")
        print_result({"size": len(file_bytes), "type": type(file_bytes).__name__})
        assert isinstance(file_bytes, bytes), "Should return bytes!"
    except SandboxError as e:
        print(f"✗ Failed to download file: {e}")
    
    # Test 2.11: Write binary content (base64)
    print_test("2.11 Write Binary Content")
    binary_file = "/workspace/binary_test.bin"
    import base64
    binary_data = b"Binary data: \x00\x01\x02\x03\xFF"
    try:
        # Write as base64
        sandbox.write(binary_file, base64.b64encode(binary_data).decode('utf-8'))
        print(f"✓ Binary file written: {binary_file}")
    except SandboxError as e:
        print(f"✗ Failed to write binary file: {e}")
    
    # Test 2.12: Delete a file
    print_test("2.12 Delete File")
    try:
        sandbox.delete(moved_file)
        print(f"✓ File deleted: {moved_file}")
        assert not sandbox.exists(moved_file), "File should not exist after deletion!"
    except SandboxError as e:
        print(f"✗ Failed to delete file: {e}")


def test_command_execution(sandbox: Sandbox):
    """Test command execution."""
    print_section("3. Command Execution Tests")
    
    # Test 3.1: Execute simple command
    print_test("3.1 Execute Simple Command")
    try:
        result = sandbox.run("echo 'Hello from sandbox'")
        print("✓ Command executed")
        print_result(result)
        assert result.get('success') == True or result.get('exitCode') == 0
    except SandboxError as e:
        print(f"✗ Failed to execute command: {e}")
    
    # Test 3.2: Execute command with output
    print_test("3.2 Execute Command with Output")
    try:
        result = sandbox.run("ls -la /workspace")
        print("✓ Command executed with output")
        print_result(result)
    except SandboxError as e:
        print(f"✗ Failed to execute command: {e}")
    
    # Test 3.3: Execute command that fails (non-zero exit code)
    print_test("3.3 Execute Command with Non-zero Exit Code")
    try:
        result = sandbox.run("false")  # This should return exit code 1
        print("✓ Command executed (expected to fail)")
        print_result(result)
        # Note: Server returns 200 even for failed commands
        assert result.get('exitCode') != 0 or result.get('success') == False
    except SandboxError as e:
        print(f"✗ Command execution error: {e}")
    
    # Test 3.4: Execute command with environment variables
    print_test("3.4 Execute Command with Environment Variables")
    try:
        # First set env vars
        sandbox.set_env_vars({"TEST_VAR": "test_value", "ANOTHER_VAR": "another_value"})
        result = sandbox.run("echo $TEST_VAR")
        print("✓ Command executed with env vars")
        print_result(result)
    except SandboxError as e:
        print(f"✗ Failed to execute command with env vars: {e}")
    
    # Test 3.5: Execute Python script
    print_test("3.5 Execute Python Script")
    python_script = """
import sys
import json

data = {
    "message": "Hello from Python",
    "version": sys.version.split()[0],
    "platform": sys.platform
}
print(json.dumps(data))
"""
    try:
        result = sandbox.run_script(python_script, interpreter="python3")
        print("✓ Python script executed")
        print_result(result)
    except SandboxError as e:
        print(f"✗ Failed to execute Python script: {e}")
    
    # Test 3.6: Execute bash script
    print_test("3.6 Execute Bash Script")
    bash_script = """#!/bin/bash
echo "Hello from Bash"
echo "Current directory: $(pwd)"
echo "User: $(whoami)"
"""
    try:
        result = sandbox.run_script(bash_script, interpreter="bash")
        print("✓ Bash script executed")
        print_result(result)
    except SandboxError as e:
        print(f"✗ Failed to execute Bash script: {e}")
    
    # Test 3.7: Execute command with working directory
    print_test("3.7 Execute Command in Specific Directory")
    try:
        # Create a directory and change to it
        test_cwd = "/workspace/cwd_test"
        sandbox.mkdir(test_cwd, recursive=True)
        # Note: cwd is set per session, so we'd need a session for this
        # For now, just test that the command works
        result = sandbox.run(f"cd {test_cwd} && pwd")
        print("✓ Command executed in directory")
        print_result(result)
    except SandboxError as e:
        print(f"✗ Failed to execute command in directory: {e}")


def test_session_management(sandbox: Sandbox):
    # """Test session management."""
    # print_section("4. Session Management Tests")
    #
    # # Test 4.1: Create a new session
    # print_test("4.1 Create Session")
    # session_id = f"test-session-{int(time.time())}"
    # try:
    #     session = sandbox.create_or_get_session(session_id)
    #     print(f"✓ Session created: {session_id}")
    #     print_result({"session_id": session.session_id})
    # except SandboxError as e:
    #     print(f"✗ Failed to create session: {e}")
    #     return None
    #
    # # Test 4.2: Create session with environment variables
    # print_test("4.2 Create Session with Environment Variables")
    # session_id_env = f"test-session-env-{int(time.time())}"
    # try:
    #     env_vars = {"SESSION_VAR": "session_value", "CUSTOM_ENV": "custom"}
    #     session_env = sandbox.create_or_get_session(
    #         session_id_env,
    #         env=env_vars,
    #         cwd="/workspace"
    #     )
    #     print(f"✓ Session created with env vars: {session_id_env}")
    #     print_result({"session_id": session_env.session_id, "env": env_vars})
    # except SandboxError as e:
    #     print(f"✗ Failed to create session with env: {e}")
    #
    # # Test 4.3: Get existing session
    # print_test("4.3 Get Existing Session")
    # try:
    #     existing_session = sandbox.create_or_get_session(session_id)
    #     print(f"✓ Retrieved existing session: {session_id}")
    #     assert existing_session.session_id == session_id
    # except SandboxError as e:
    #     print(f"✗ Failed to get existing session: {e}")
    #
    # # Test 4.4: Execute command in session
    # print_test("4.4 Execute Command in Session")
    # try:
    #     result = session.run("echo 'Command in session'")
    #     print("✓ Command executed in session")
    #     print_result(result)
    # except SandboxError as e:
    #     print(f"✗ Failed to execute command in session: {e}")
    #
    # # Test 4.5: File operations in session
    # print_test("4.5 File Operations in Session")
    # session_file = "/workspace/session_file.txt"
    # try:
    #     session.write(session_file, "Content from session")
    #     content = session.read(session_file)
    #     print("✓ File operations in session")
    #     print_result({"content": content})
    #     assert content == "Content from session"
    # except SandboxError as e:
    #     print(f"✗ Failed file operations in session: {e}")
    #
    # Test 4.6: Multiple sessions isolation
    print_test("4.6 Multiple Sessions Isolation")
    session1_id = f"session1-{int(time.time())}"
    session2_id = f"session2-{int(time.time())}"
    try:
        env_vars1 = {"SESSION_VAR": "session_value", "CUSTOM_ENV": "custom1"}
        env_vars2 = {"SESSION_VAR": "session_value", "CUSTOM_ENV": "custom2"}
        sandbox.mkdir("/workspace/session1",recursive=True)
        sandbox.mkdir("/workspace/session2", recursive=True)
        session1 = sandbox.create_or_get_session(session1_id, cwd="/workspace/session1",env=env_vars1)
        session2 = sandbox.create_or_get_session(session2_id, cwd="/workspace/session2",env=env_vars2)

        result=session1.run("echo  $CUSTOM_ENV")
        print_result(result)
        result=session2.run("echo  $CUSTOM_ENV")
        print_result(result)

        result = sandbox.run("pwd")
        #sandbox 在workspace 新开的session实际就是开了shell然后在自己的root 但是可以预先创建目录然后cwd过去
        print_result(result)
        print("------------")
        result = session1.run("ls")
        print_result(result)
        result=session1.run("pwd")
        print_result(result)
        result=session2.run("pwd")
        print_result(result)
        # Create files in each session
        session1.write("/workspace/file.txt", "Session 1 content")
        result = session1.run("ls")
        print_result(result)
        session2.write("/workspace/file.txt", "Session 2 content")
        result = session2.run("ls")
        print_result(result)

        # # Verify isolation (files should be accessible from default session too since filesystem is shared)
        content1 = sandbox.read("/workspace/file.txt")
        content2 = sandbox.read("/workspace/file.txt")

        print("✓ Multiple sessions created and isolated")
        print_result({
            "session1_file": content1,
            "session2_file": content2
        })
    except SandboxError as e:
        print(f"✗ Failed to test session isolation: {e}")
    
    # Test 4.7: Delete session
    # print_test("4.7 Delete Session")
    # try:
    #     result = sandbox.delete_session(session_id_env)
    #     print(f"✓ Session deleted: {session_id_env}")
    #     print_result(result)
    # except SandboxError as e:
    #     print(f"✗ Failed to delete session: {e}")
    #
    # return session


def test_error_handling(manager: SandboxManager, sandbox: Sandbox):
    """Test error handling scenarios."""
    print_section("5. Error Handling Tests")
    
    # Test 5.1: Read non-existent file
    print_test("5.1 Read Non-existent File")
    try:
        sandbox.read("/workspace/non_existent_file.txt")
        print("✗ Should have raised an error!")
    except SandboxError as e:
        print(f"✓ Correctly raised error: {e.status_code} - {e}")
    
    # Test 5.2: Delete non-existent file
    print_test("5.2 Delete Non-existent File")
    try:
        sandbox.delete("/workspace/non_existent_file.txt")
        print("✗ Should have raised an error!")
    except SandboxError as e:
        print(f"✓ Correctly raised error: {e.status_code} - {e}")
    
    # Test 5.3: Delete non-existent session
    print_test("5.3 Delete Non-existent Session")
    try:
        sandbox.delete_session("non-existent-session-id")
        print("✗ Should have raised an error!")
    except SandboxError as e:
        print(f"✓ Correctly raised error: {e.status_code} - {e}")
    
    # Test 5.4: Rename non-existent file
    print_test("5.4 Rename Non-existent File")
    try:
        sandbox.rename("/workspace/non_existent.txt", "/workspace/new_name.txt")
        print("✗ Should have raised an error!")
    except SandboxError as e:
        print(f"✓ Correctly raised error: {e.status_code} - {e}")


def test_bucket_operations(sandbox: Sandbox):
    """Test bucket mounting operations (requires configuration)."""
    print_section("6. Bucket Operations Tests")
    
    # Note: These tests require actual bucket configuration
    # They are included as examples but will likely fail without proper setup
    
    # Test 6.1: Mount bucket (example - requires configuration)
    print_test("6.1 Mount Bucket (Example - Requires Configuration)")
    print("  Note: This test requires valid bucket credentials and endpoint.")
    print("  Uncomment and configure the following code to test:")
    print("""
    try:
        bucket_options = {
            "endpoint": "https://your-bucket-endpoint.com",
            "provider": "s3",  # or "r2", "gcs"
            "credentials": {
                "accessKeyId": "your-access-key",
                "secretAccessKey": "your-secret-key"
            },
            "readOnly": False
        }
        result = sandbox.mount_bucket("my-bucket", "/mnt/bucket", bucket_options)
        print("✓ Bucket mounted")
        print_result(result)
    except SandboxError as e:
        print(f"✗ Failed to mount bucket: {e}")
    """)
    
    # Test 6.2: Unmount bucket (example)
    print_test("6.2 Unmount Bucket (Example - Requires Configuration)")
    print("  Note: This test requires a previously mounted bucket.")
    print("  Uncomment and configure the following code to test:")
    print("""
    try:
        result = sandbox.unmount_bucket("/mnt/bucket")
        print("✓ Bucket unmounted")
        print_result(result)
    except SandboxError as e:
        print(f"✗ Failed to unmount bucket: {e}")
    """)
    
    # Test 6.3: Mount bucket in session (example)
    print_test("6.3 Mount Bucket in Session (Example - Requires Configuration)")
    print("  Note: This test requires valid bucket credentials.")
    print("  Uncomment and configure the following code to test:")
    print("""
    try:
        session = sandbox.create_or_get_session("bucket-session")
        bucket_options = {
            "endpoint": "https://your-bucket-endpoint.com",
            "provider": "s3",
            "credentials": {
                "accessKeyId": "your-access-key",
                "secretAccessKey": "your-secret-key"
            }
        }
        result = session.mount_bucket("my-bucket", "/mnt/session-bucket", bucket_options)
        print("✓ Bucket mounted in session")
        print_result(result)
    except SandboxError as e:
        print(f"✗ Failed to mount bucket in session: {e}")
    """)


def test_advanced_scenarios(sandbox: Sandbox):
    """Test advanced usage scenarios."""
    print_section("7. Advanced Scenarios")
    
    # Test 6.1: Create a complete project structure
    print_test("6.1 Create Project Structure")
    project_root = "/workspace/my_project"
    try:
        # Create directory structure
        sandbox.mkdir(f"{project_root}/src", recursive=True)
        sandbox.mkdir(f"{project_root}/tests", recursive=True)
        sandbox.mkdir(f"{project_root}/docs", recursive=True)
        
        # Create files
        sandbox.write(f"{project_root}/README.md", "# My Project\n\nThis is a test project.")
        sandbox.write(f"{project_root}/src/main.py", "print('Hello from main.py')")
        sandbox.write(f"{project_root}/src/utils.py", "def helper(): return 'help'")
        sandbox.write(f"{project_root}/tests/test_main.py", "def test_main(): assert True")
        
        # Verify structure
        result = sandbox.run(f"find {project_root} -type f | sort")
        print("✓ Project structure created")
        print_result(result)
    except SandboxError as e:
        print(f"✗ Failed to create project structure: {e}")
    
    # Test 6.2: Run a multi-step workflow
    print_test("6.2 Multi-step Workflow")
    try:
        # Step 1: Create a Python script
        script_path = "/workspace/workflow_script.py"
        script_content = """
import os
import json

# Create output directory
os.makedirs('/workspace/output', exist_ok=True)

# Generate data
data = {
    'timestamp': '2024-01-01T00:00:00Z',
    'status': 'success',
    'items': [1, 2, 3, 4, 5]
}

# Write to file
with open('/workspace/output/data.json', 'w') as f:
    json.dump(data, f, indent=2)

print('Workflow completed successfully')
"""
        sandbox.write(script_path, script_content)
        
        # Step 2: Execute the script
        result = sandbox.run_script(script_path, interpreter="python3")
        
        # Step 3: Verify output
        output_content = sandbox.read("/workspace/output/data.json")
        
        print("✓ Multi-step workflow completed")
        print_result({
            "script_result": result.get('output', ''),
            "output_file": output_content[:200] if len(output_content) > 200 else output_content
        })
    except SandboxError as e:
        print(f"✗ Failed multi-step workflow: {e}")
    
    # Test 6.3: File manipulation workflow
    print_test("6.3 File Manipulation Workflow")
    try:
        # Create initial file
        initial_file = "/workspace/workflow_data.txt"
        sandbox.write(initial_file, "Initial content\nLine 2\nLine 3")
        
        # Read and modify
        content = sandbox.read(initial_file)
        modified_content = content + "\nModified line"
        
        # Write modified content
        sandbox.write(initial_file, modified_content)
        
        # Move to archive
        archive_file = "/workspace/archive/workflow_data.txt"
        sandbox.mkdir("/workspace/archive", recursive=True)
        sandbox.move(initial_file, archive_file)
        
        # Verify
        archived_content = sandbox.read(archive_file)
        
        print("✓ File manipulation workflow completed")
        print_result({
            "original_lines": len(content.split('\n')),
            "modified_lines": len(modified_content.split('\n')),
            "archived": sandbox.exists(archive_file)
        })
    except SandboxError as e:
        print(f"✗ Failed file manipulation workflow: {e}")


def main():
    """Run all test examples."""
    print("\n" + "=" * 80)
    print("  Cloudflare Sandbox SDK - Comprehensive Test Examples")
    print("=" * 80)
    
    # Initialize manager
    base_url = os.environ.get("SANDBOX_BASE_URL", "http://localhost:8787")
    manager = SandboxManager(base_url=base_url)
    print(f"\nUsing base URL: {base_url}")
    
    try:
        # Run all test suites
        sandbox = test_lifecycle_management(manager)
        if sandbox:
            # test_file_operations(sandbox)
            # test_command_execution(sandbox)
            # test_session_management(sandbox)
            test_error_handling(manager, sandbox)
            # test_bucket_operations(sandbox)
            # test_advanced_scenarios(sandbox)
        
        print_section("Test Summary")
        print("✓ All test suites completed!")
        print("\nNote: Some tests may show errors for expected failure cases (error handling tests).")
        
        # Cleanup
        if sandbox:
            print("\n[Cleanup] Destroying test sandbox...")
            try:
                manager.destroy_sandbox(sandbox.sandbox_id)
                print(f"✓ Sandbox destroyed: {sandbox.sandbox_id}")
            except SandboxError as e:
                print(f"✗ Failed to destroy sandbox: {e}")
    
    except KeyboardInterrupt:
        print("\n\n[Interrupted] Tests interrupted by user.")
    except Exception as e:
        print(f"\n\n[Error] Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

