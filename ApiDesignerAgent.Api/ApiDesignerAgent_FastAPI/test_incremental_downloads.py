"""
Test script for incremental code generation downloads.
Requires a running server: python run.py
Usage: python test_incremental_downloads.py
"""

import requests
import time
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"


def get_token(username="admin", password="admin1234"):
    """Get auth token. Register user if not exists."""
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      data={"username": username, "password": password})
    if r.status_code == 200:
        return r.json()["access_token"]
    # Try registering
    requests.post(f"{BASE_URL}/api/auth/register",
                  json={"username": username, "email": f"{username}@test.com", "password": password})
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      data={"username": username, "password": password})
    return r.json().get("access_token", "")

def test_incremental_downloads():
    """Test incremental download functionality."""
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Sample OpenAPI spec
    openapi_yaml = """
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /api/users:
    get:
      summary: Get all users
      responses:
        '200':
          description: Success
components:
  schemas:
    User:
      type: object
      properties:
        id:
          type: string
          format: uuid
        name:
          type: string
        email:
          type: string
    """
    
    # Start code generation
    print("Starting code generation...")
    response = requests.post(
        f"{BASE_URL}/api/codegen/generate-dotnet",
        json={
            "open_api_yaml": openapi_yaml,
            "project_name": "TestApi",
            "llm_provider": "groq",
            "include_tests": False
        },
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to start generation: {response.text}")
        return
    
    result = response.json()
    job_id = result["job_id"]
    print(f"✅ Job started: {job_id}")
    print(f"📡 Stream URL: {result['stream_url']}")
    
    # Create output directory
    output_dir = Path("generated_code_incremental")
    output_dir.mkdir(exist_ok=True)
    
    # Download latest code every 30 seconds
    print("\n⏳ Downloading code incrementally (press Ctrl+C to stop)...")
    download_count = 0
    
    try:
        while True:
            time.sleep(30)  # Wait 30 seconds between downloads
            
            try:
                download_count += 1
                print(f"\n📥 Download attempt #{download_count}...")
                
                response = requests.get(
                    f"{BASE_URL}/api/codegen/download/{job_id}/latest",
                    timeout=10
                )
                
                if response.status_code == 200:
                    filename = output_dir / f"TestApi_v{download_count}.zip"
                    with open(filename, "wb") as f:
                        f.write(response.content)
                    
                    size_kb = len(response.content) / 1024
                    print(f"✅ Downloaded: {filename} ({size_kb:.1f} KB)")
                    
                elif response.status_code == 404:
                    print("⏳ Code generation not started yet, waiting...")
                    
                else:
                    print(f"⚠️  Status {response.status_code}: {response.text[:100]}")
                    
            except requests.exceptions.Timeout:
                print("⏱️  Request timeout, will retry...")
            except requests.exceptions.RequestException as e:
                print(f"⚠️  Request error: {e}")
                
    except KeyboardInterrupt:
        print("\n\n🛑 Stopped by user")
    
    # Try to download final version
    print("\n📥 Attempting to download final version...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/codegen/download/{job_id}/final",
            timeout=10
        )
        
        if response.status_code == 200:
            filename = output_dir / "TestApi_Final.zip"
            with open(filename, "wb") as f:
                f.write(response.content)
            print(f"✅ Final version downloaded: {filename}")
        else:
            print(f"⚠️  Final version not ready yet (status {response.status_code})")
    except Exception as e:
        print(f"⚠️  Could not download final: {e}")
    
    print(f"\n✨ All downloads saved to: {output_dir.absolute()}")


def test_step_specific_downloads():
    """Test downloading specific steps."""
    
    job_id = input("Enter job_id: ").strip()
    
    steps = [
        "2_solution",
        "3_auth", 
        "4_entities_dtos",
        "5_data_layer",
        "6_business_layer",
        "7_controllers",
        "8_program"
    ]
    
    output_dir = Path("generated_code_steps")
    output_dir.mkdir(exist_ok=True)
    
    print(f"\n📥 Downloading individual steps for job {job_id}...\n")
    
    for step in steps:
        try:
            response = requests.get(
                f"{BASE_URL}/api/codegen/download/{job_id}/step-{step}",
                timeout=10
            )
            
            if response.status_code == 200:
                filename = output_dir / f"step-{step}.zip"
                with open(filename, "wb") as f:
                    f.write(response.content)
                size_kb = len(response.content) / 1024
                print(f"✅ {step:20s} - {size_kb:6.1f} KB - {filename}")
            elif response.status_code == 404:
                print(f"⏳ {step:20s} - Not ready yet")
            else:
                print(f"⚠️  {step:20s} - Status {response.status_code}")
                
        except Exception as e:
            print(f"❌ {step:20s} - Error: {e}")
    
    print(f"\n✨ Step downloads saved to: {output_dir.absolute()}")


if __name__ == "__main__":
    print("=" * 60)
    print("Incremental Code Generation Download Test")
    print("=" * 60)
    print("\nOptions:")
    print("1. Test incremental downloads (auto-download every 30s)")
    print("2. Download specific steps (requires job_id)")
    print()
    
    choice = input("Choose option (1 or 2): ").strip()
    
    if choice == "1":
        test_incremental_downloads()
    elif choice == "2":
        test_step_specific_downloads()
    else:
        print("Invalid choice")
