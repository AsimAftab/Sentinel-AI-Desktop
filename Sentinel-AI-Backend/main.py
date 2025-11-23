# main.py

import os
from dotenv import load_dotenv

print("--- 1. Script started: main.py ---")

# Load environment variables from .env file
print("--- 2. Attempting to load .env file... ---")
load_dotenv()
print("--- 3. .env file processed. Now checking for the key... ---")

# --- Diagnostic Check ---
# Let's immediately check if the key was loaded into the environment.
tavily_key = os.getenv("TAVILY_API_KEY")

if tavily_key:
    # We only print the first few characters for security.
    print(f"--- 4. ✅ SUCCESS: Found TAVILY_API_KEY starting with '{tavily_key[:4]}...' ---")
else:
    print("\n--- 4. ❌ FAILED: TAVILY_API_KEY was NOT FOUND in the environment. ---")
    print("--- STOPPING. Please check your .env file setup. ---\n")
    # We stop the program here because there's no point in continuing.
    exit()

# --- If the check above passes, we proceed ---
print("--- 5. Key found successfully. Now importing the rest of the application... ---")

# Check LangSmith configuration
langsmith_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
langsmith_project = os.getenv("LANGCHAIN_PROJECT", "default")
if langsmith_enabled:
    print(f"--- 5a. 🔍 LangSmith tracing ENABLED for project: '{langsmith_project}' ---")
    print("--- 5b. View traces at: https://smith.langchain.com ---")
else:
    print("--- 5a. ℹ️ LangSmith tracing disabled. Set LANGCHAIN_TRACING_V2=true to enable. ---")

# This import will trigger the chain reaction that leads to Tavily being initialized.
from src.utils.orchestrator import run_sentinel_agent

print("--- 6. Application imported successfully. ---")


if __name__ == "__main__":
    print("--- 7. Handing control to the agent orchestrator... ---")
    run_sentinel_agent()