import os

from artifact_sandbox.client.client import SandboxManager, SandboxError


def main() -> None:
    """
    Minimal demo of manager + Sandbox usage for manual API verification.

    - Create/ensure a sandbox
    - Write/read/delete a file
    - Destroy a sandbox
    - Remove all sandboxes
    """
    manager = SandboxManager()
    sandbox_id = "demo-client2"

    # Ensure the container exists
    sbx = manager.create_or_get_sandbox(sandbox_id, options={"keepAlive": True})
    print("create_sandbox success, sandbox_id:", sbx.sandbox_id)

    # Write file
    sbx.write("/workspace/hello.txt", "hi from client2")
    print("write success")

    # Read file
    content = sbx.read("/workspace/hello.txt")
    print("read success, content:", content)

    # Run a command
    result = sbx.run("ls -la /workspace")
    print("run success, result:", result)

    # ==========================================
    # Python script examples
    # ==========================================
    print("\n" + "=" * 50)
    print("Python script examples")
    print("=" * 50)

    # Python example 1: run from local file path
    python_script_path = "./test_python.py"
    with open(python_script_path, "w", encoding="utf-8") as f:
        f.write("""#!/usr/bin/env python3
import sys
import json

print("Hello from Python!")
print(f"Python version: {sys.version}")

data = {"numbers": [1, 2, 3, 4, 5]}
print(f"Data: {json.dumps(data, indent=2)}")

for i in range(3):
    print(f"Count: {i}")
""")

    python_result = sbx.run_script(python_script_path, interpreter="python3")
    print("✅ Python script (from file) executed successfully")
    print(f"Output: {python_result.get('output')}")
    print(f"Script path: {python_result.get('scriptPath')}")

    # Python example 2: pass script content directly
    python_content = """
import math
result = sum([i**2 for i in range(1, 6)])
print(f"1² + 2² + 3² + 4² + 5² = {result}")
"""
    python_content_result = sbx.run_script(python_content, interpreter="python3")
    print("✅ Python script (from content) executed successfully")
    print(f"Output: {python_content_result.get('output')}")

    # Clean up Python test file
    if os.path.exists(python_script_path):
        os.remove(python_script_path)

    # ==========================================
    # Bash script examples
    # ==========================================
    print("\n" + "=" * 50)
    print("Bash script examples")
    print("=" * 50)

    # Bash example 1: run from local file path
    bash_script_path = "./test_bash.sh"
    with open(bash_script_path, "w", encoding="utf-8") as f:
        f.write("""#!/bin/bash
echo "Hello from Bash!"
echo "Current directory: $(pwd)"
echo "User: $(whoami)"
echo "Date: $(date)"

# Loop example
for i in {1..5}; do
    echo "Iteration $i"
done

# Arithmetic example
sum=$((10 + 20 + 30))
echo "Sum: $sum"
""")

    bash_result = sbx.run_script(bash_script_path, interpreter="bash")
    print("✅ Bash script (from file) executed successfully")
    print(f"Output: {bash_result.get('output')}")
    print(f"Script path: {bash_result.get('scriptPath')}")

    # Bash example 2: pass script content directly
    bash_content = """
#!/bin/bash
echo "Quick bash test"
echo "Files in /workspace:"
ls -lh /workspace | head -5
"""
    bash_content_result = sbx.run_script(bash_content, interpreter="bash")
    print("✅ Bash script (from content) executed successfully")
    print(f"Output: {bash_content_result.get('output')}")

    # Clean up Bash test file
    if os.path.exists(bash_script_path):
        os.remove(bash_script_path)

    # ==========================================
    # Node.js script examples
    # ==========================================
    print("\n" + "=" * 50)
    print("Node.js script examples")
    print("=" * 50)

    # Node.js example 1: run from local file path
    node_script_path = "./test_node.js"
    with open(node_script_path, "w", encoding="utf-8") as f:
        f.write("""// Node.js script example
const os = require('os');
const fs = require('fs');

console.log('Hello from Node.js!');
console.log(`Node version: ${process.version}`);
console.log(`Platform: ${os.platform()}`);

// Array manipulation example
const numbers = [1, 2, 3, 4, 5];
const doubled = numbers.map(n => n * 2);
console.log(`Original: [${numbers.join(', ')}]`);
console.log(`Doubled: [${doubled.join(', ')}]`);

// Simple reduce example
const sum = numbers.reduce((acc, n) => acc + n, 0);
console.log(`Sum: ${sum}`);
""")

    try:
        node_result = sbx.run_script(node_script_path, interpreter="node")
        print("✅ Node.js script (from file) executed successfully")
        print(f"Output: {node_result.get('output')}")
        print(f"Script path: {node_result.get('scriptPath')}")
    except SandboxError as e:
        print(f"⚠️ Node.js may not be installed: {e}")

    # Node.js example 2: pass script content directly
    node_content = """
console.log('Quick Node.js test');
const arr = [1, 2, 3];
console.log(`Array length: ${arr.length}`);
"""
    try:
        node_content_result = sbx.run_script(node_content, interpreter="node")
        print("✅ Node.js script (from content) executed successfully")
        print(f"Output: {node_content_result.get('output')}")
    except SandboxError as e:
        print(f"⚠️ Node.js may not be installed: {e}")

    # Clean up Node.js test file
    if os.path.exists(node_script_path):
        os.remove(node_script_path)

    # ==========================================
    # Shell script example (sh)
    # ==========================================
    print("\n" + "=" * 50)
    print("Shell script example (sh)")
    print("=" * 50)

    sh_content = """
#!/bin/sh
echo "Hello from sh!"
echo "Environment test:"
env | grep -E '^(PATH|HOME|USER)=' | head -3
"""
    sh_result = sbx.run_script(sh_content, interpreter="sh")
    print("✅ Shell script (sh) executed successfully")
    print(f"Output: {sh_result.get('output')}")

    # ==========================================
    # Summary
    # ==========================================
    print("\n" + "=" * 50)
    print("Script execution summary")
    print("=" * 50)
    print("✅ Demonstrated running scripts for multiple languages:")
    print("   Python3 - from file and from content")
    print("   Bash - from file and from content")
    print("   Node.js - from file and from content")
    print("   Shell (sh) - from content")
    print("=" * 50 + "\n")

    # Delete file
    sbx.delete("/workspace/hello.txt")
    print("delete success")

    # Destroy a single sandbox
    manager.destroy_sandbox(sandbox_id)
    print("destroy_sandbox success")

    # Demonstrate removing all sandboxes (if multiple exist)
    # Create a few sandboxes first
    for i in range(3):
        manager.create_or_get_sandbox(f"demo-{i}", options={"keepAlive": True})

    # Remove all sandboxes
    result = manager.destroy_all_sandboxes(continue_on_error=True)
    print("destroy_all_sandboxes result:", result)


if __name__ == "__main__":
    main()