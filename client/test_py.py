import sys
import os

print("Python version:", sys.version)
print("Current directory:", os.getcwd())
print("Environment variable TEST:", os.environ.get("TEST", "not set"))