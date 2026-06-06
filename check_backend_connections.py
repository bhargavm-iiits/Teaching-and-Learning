#!/usr/bin/env python
"""
Diagnostic script to check backend connections for the AI-Driven Personalized VR Teaching System.
Verifies configuration variables and tests connectivity to Supabase, Pinecone, and Qwen (DashScope) APIs,
as well as Unity connectivity status and local ports.
"""

import sys
import os

# Define color helpers for terminal output
def print_success(msg):
    print(f"\033[92m✔ {msg}\033[0m")

def print_failure(msg):
    print(f"\033[91m✘ {msg}\033[0m")

def print_warning(msg):
    print(f"\033[93m⚠ {msg}\033[0m")

def print_info(msg):
    print(f"\033[94mℹ {msg}\033[0m")

def print_header(title):
    print("\n" + "=" * 60)
    print(f" {title} ".center(60, "="))
    print("=" * 60)

# 1. Check imports
print_header("Step 1: Checking Required Packages")
required_modules = {
    "dotenv": "python-dotenv",
    "openai": "openai",
    "pinecone": "pinecone",
    "supabase": "supabase",
    "langchain_openai": "langchain-openai",
    "fastapi": "fastapi",
    "httpx": "httpx"
}

missing_modules = []
for module_name, pip_name in required_modules.items():
    try:
        __import__(module_name)
        print_success(f"Module '{module_name}' is installed.")
    except ImportError:
        print_failure(f"Module '{module_name}' is NOT installed.")
        missing_modules.append(pip_name)

if missing_modules:
    print("\n" + "!" * 60)
    print_warning("Some required Python packages are missing!")
    print(f"Please install them by running: \n\033[96mpip install -r requirements.txt\033[0m")
    print("!" * 60)
    sys.exit(1)
else:
    print_success("All required packages are available.")

# Import verified packages
from dotenv import load_dotenv
load_dotenv(override=True)

# 2. Check environment variables
print_header("Step 2: Checking Environment Variables (.env)")

keys_to_check = {
    "DASHSCOPE_API_KEY": "Qwen / DashScope API Key",
    "QWEN_MODEL": "Qwen Model ID",
    "SUPABASE_URL": "Supabase Project URL",
    "SUPABASE_KEY": "Supabase Anon/Public Key",
    "SUPABASE_SERVICE_KEY": "Supabase Service Role Key (Optional)",
    "PINECONE_API_KEY": "Pinecone API Key",
    "PINECONE_HOST": "Pinecone Index Host URL",
    "AZURE_OPENAI_DEPLOYMENT_NAME": "Azure OpenAI Deployment Name (Optional)",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "Azure OpenAI Embeddings Deployment (Optional)"
}

missing_keys = []
for key, desc in keys_to_check.items():
    val = os.getenv(key)
    if not val:
        if "Optional" in desc:
            print_info(f"{key} ({desc}) is not set. (Optional)")
        else:
            print_failure(f"{key} ({desc}) is NOT set!")
            missing_keys.append(key)
    else:
        # Mask the key for security
        masked = val
        if len(val) > 8:
            masked = val[:4] + "..." + val[-4:]
        else:
            masked = "set"
        print_success(f"{key} is set: {masked} ({desc})")

if missing_keys:
    print("\n" + "!" * 60)
    print_warning(f"Missing required environment variables: {', '.join(missing_keys)}")
    print("Please configure them in your .env file before proceeding.")
    print("!" * 60)
    # Don't exit here, attempt to test whatever we can.

# 3. Test Qwen (DashScope) connection
print_header("Step 3: Testing Qwen / DashScope API Connection")
dashscope_key = os.getenv("DASHSCOPE_API_KEY")
qwen_model = os.getenv("QWEN_MODEL", "qwen3.6-plus")

if not dashscope_key:
    print_failure("Skipping DashScope test: DASHSCOPE_API_KEY is not set.")
else:
    try:
        from openai import OpenAI
        print_info(f"Connecting to DashScope using model: {qwen_model}...")
        client = OpenAI(
            api_key=dashscope_key,
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
        # Quick hello request
        response = client.chat.completions.create(
            model=qwen_model,
            messages=[{"role": "user", "content": "Say hello!"}],
            max_tokens=10
        )
        reply = response.choices[0].message.content.strip()
        print_success("Successfully connected to Qwen/DashScope API!")
        print_info(f"Response from model: {reply}")
    except Exception as e:
        print_failure(f"Failed to connect to Qwen/DashScope API: {e}")

# 4. Test Supabase connection
print_header("Step 4: Testing Supabase Database Connection")
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    print_failure("Skipping Supabase test: URL or Key is not set.")
else:
    try:
        from supabase import create_client
        print_info(f"Connecting to Supabase at: {supabase_url}...")
        sp_client = create_client(supabase_url, supabase_key)
        
        # Test basic schema by querying the 'classes' table
        print_info("Querying 'classes' table...")
        response = sp_client.table("classes").select("*").limit(1).execute()
        print_success("Successfully connected to Supabase Database!")
        print_info(f"Found {len(response.data)} records in 'classes' table.")
    except Exception as e:
        print_failure(f"Failed to connect to Supabase: {e}")
        print_info("Note: Please make sure that your Supabase instance is active and 'classes' table exists.")

# 5. Test Pinecone connection
print_header("Step 5: Testing Pinecone Vector Database Connection")
pinecone_key = os.getenv("PINECONE_API_KEY")
pinecone_host = os.getenv("PINECONE_HOST")

if not pinecone_key or not pinecone_host:
    print_failure("Skipping Pinecone test: API Key or Host is not set.")
else:
    try:
        from pinecone import Pinecone
        print_info("Connecting to Pinecone...")
        pc = Pinecone(api_key=pinecone_key)
        index = pc.Index(host=pinecone_host)
        
        print_info("Fetching index stats...")
        stats = index.describe_index_stats()
        print_success("Successfully connected to Pinecone Vector Database!")
        print_info(f"Index Dimensions: {stats.dimension}")
        print_info(f"Total Vector Count: {stats.total_vector_count}")
        print_info(f"Available Namespaces: {list(stats.namespaces.keys())}")
    except Exception as e:
        print_failure(f"Failed to connect to Pinecone: {e}")

# 6. Check Unity Connectivity & Port Availability
print_header("Step 6: Unity Connectivity & Port Discovery")

print_info("Understanding the Unity & Backend Architecture:")
print("  - The FastAPI server acts as a SERVER (listening on port 8000/8080 by default).")
print("  - The Unity VR application acts as a CLIENT. It connects to the backend server.")
print("  - The backend serves lesson manifests & C# scripts that reference prefabs.")
print("  - The Unity Client loads assets locally from its own Project folder.")
print("  - Therefore, the backend does not 'fetch' assets from Unity; Unity reads metadata from the backend.")

# Check if port 8000 is open/bound (if FastAPI is running)
import socket
def check_port(port) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

port_8000_open = check_port(8000)
port_8080_open = check_port(8080)
server_active = False

for port in [8000, 8080]:
    if check_port(port):
        try:
            import httpx
            r = httpx.get(f"http://localhost:{port}/health", timeout=1.0)
            if r.status_code == 200:
                print_success(f"FastAPI Server is ALREADY RUNNING on port {port}!")
                print_info(f"Unity can connect right now to: ws://localhost:{port}/ws/lesson")
                server_active = True
                break
        except Exception:
            pass

if not server_active:
    if port_8000_open:
        print_warning("Port 8000 is in use, but not responding to our FastAPI health check. Another process is using it.")
    else:
        print_info("FastAPI Backend Server is not currently running. (This is normal - start it with 'python main.py')")

# Check for running Unity Editor processes on this Windows PC
try:
    import subprocess
    tasklist_out = subprocess.check_output("tasklist", shell=True, text=True)
    
    unity_running = "Unity.exe" in tasklist_out
    unity_hub_running = "Unity Hub.exe" in tasklist_out
    
    if unity_running:
        print_success("Unity Editor is currently RUNNING on this PC!")
        print_info("Once you start your FastAPI backend server, the Unity client will be able to connect and fetch/compile assets instantly.")
    elif unity_hub_running:
        print_warning("Unity Hub is running, but the Unity Editor itself is NOT open. Please open your project in Unity Editor.")
    else:
        print_failure("Unity Editor is NOT running on this PC. Please launch Unity Editor and load your VR teaching project.")
except Exception as e:
    print_warning(f"Could not scan running processes on Windows: {e}")

print_header("Diagnostics Completed")
print("If all critical checks passed, your backend is ready to run!")
print("To start the backend, run: \n\033[96mpython main.py\033[0m or \033[96muvicorn main:app --reload --port 8000\033[0m")
print("=" * 60 + "\n")
