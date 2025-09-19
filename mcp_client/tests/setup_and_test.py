#!/usr/bin/env python

"""
setup_and_test.py

Setup and testing script for the modular Insurance MCP Client with Vertex AI.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_components():
    """Test all components of the modular MCP client"""
    
    print("🧪 Testing Modular Insurance MCP Client with Vertex AI")
    print("=" * 60)
    
    # Test 1: Configuration loading
    print("\n1️⃣ Testing configuration loading...")
    try:
        from config import settings
        print(f"✅ Configuration loaded successfully")
        print(f"   Environment: {settings.environment}")
        print(f"   MCP Server: {settings.mcp.server_url}")
        print(f"   Vertex AI Project: {settings.vertex_ai.project_id}")
        print(f"   API Port: {settings.api.port}")
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        return False
    
    # Test 2: MCP Client
    print("\n2️⃣ Testing MCP client connection...")
    try:
        from mcp_client import InsuranceMCPClient
        
        client = InsuranceMCPClient()
        await client.connect()
        
        print(f"✅ MCP client connected successfully")
        print(f"   Available tools: {client.available_tools}")
        
        # Test tool calling
        if "list_documents" in client.available_tools:
            docs = await client.get_documents_list()
            print(f"   Documents found: {len(docs)}")
        
        await client.disconnect()
        
    except Exception as e:
        print(f"❌ MCP client test failed: {e}")
        print("   Make sure MCP server is running on port 8081")
    
    # Test 3: Vertex AI Client (if configured)
    print("\n3️⃣ Testing Vertex AI client...")
    try:
        from vertex_ai_client import VertexAIClient
        
        if settings.vertex_ai.credentials_path and Path(settings.vertex_ai.credentials_path).exists():
            ai_client = VertexAIClient()
            await ai_client.initialize()
            
            print(f"✅ Vertex AI client initialized successfully")
            print(f"   Model: {ai_client.model_name}")
            print(f"   Project: {ai_client.project_id}")
            
            # Test health check
            health = await ai_client.health_check()
            print(f"   Health check: {health.get('test_generation', 'N/A')}")
            
        else:
            print("⚠️ Vertex AI credentials not configured - skipping test")
            print("   Set VERTEX_AI__CREDENTIALS_PATH in .env file")
            
    except Exception as e:
        print(f"❌ Vertex AI client test failed: {e}")
    
    # Test 4: Insurance Service
    print("\n4️⃣ Testing insurance service...")
    try:
        from mcp_client.services import InsuranceService
        
        service = InsuranceService()
        # We won't initialize here as it requires both MCP and Vertex AI
        
        print(f"✅ Insurance service created successfully")
        
        # Test health check without initialization
        health = await service.health_check()
        print(f"   Service status: {health.get('overall_status', 'unknown')}")
        
    except Exception as e:
        print(f"❌ Insurance service test failed: {e}")
    
    # Test 5: FastAPI App
    print("\n5️⃣ Testing FastAPI application setup...")
    try:
        from main import app
        
        print(f"✅ FastAPI application created successfully")
        print(f"   Title: {app.title}")
        print(f"   Version: {app.version}")
        print(f"   Routes: {len(app.routes)} endpoints")
        
    except Exception as e:
        print(f"❌ FastAPI application test failed: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Component testing completed!")
    return True


def check_requirements():
    """Check if all required dependencies are installed"""
    print("📦 Checking requirements...")
    
    required_packages = [
        "mcp",
        "fastapi", 
        "uvicorn",
        "pydantic",
        "google-cloud-aiplatform",
        "psycopg",
        "python-dotenv"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} - MISSING")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install -r requirements.txt")
        return False
    
    print("✅ All required packages are installed")
    return True


def setup_environment():
    """Setup environment configuration"""
    print("⚙️ Setting up environment...")
    
    example_env = Path(".env.example")
    env_file = Path(".env")
    
    if not env_file.exists() and example_env.exists():
        print("   Creating .env file from .env.example...")
        with open(example_env) as f:
            content = f.read()
        
        with open(env_file, 'w') as f:
            f.write(content)
        
        print("   ✅ .env file created")
        print("   ⚠️ Please update .env with your actual configuration:")
        print("      - VERTEX_AI__PROJECT_ID")
        print("      - VERTEX_AI__CREDENTIALS_PATH") 
        print("      - DATABASE__PASSWORD")
        return False
    elif env_file.exists():
        print("   ✅ .env file already exists")
        return True
    else:
        print("   ❌ No .env.example file found")
        return False


def create_test_credentials():
    """Create a sample service account JSON structure for testing"""
    print("🔑 Creating sample credentials structure...")
    
    sample_creds = {
        "type": "service_account",
        "project_id": "your-project-id",
        "private_key_id": "key-id",
        "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
        "client_email": "service-account@your-project.iam.gserviceaccount.com",
        "client_id": "client-id",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/service-account%40your-project.iam.gserviceaccount.com"
    }
    
    creds_file = Path("service-account-sample.json")
    if not creds_file.exists():
        with open(creds_file, 'w') as f:
            json.dump(sample_creds, f, indent=2)
        
        print(f"   ✅ Sample credentials file created: {creds_file}")
        print("   ⚠️ Replace with your actual service account JSON file")
    else:
        print("   ✅ Credentials file already exists")


async def main():
    """Main setup and test function"""
    print("🚀 Insurance MCP Client Setup & Test")
    print("=" * 60)
    
    # Step 1: Check requirements
    if not check_requirements():
        print("\n❌ Setup failed - install missing packages first")
        return
    
    # Step 2: Setup environment
    env_ready = setup_environment()
    
    # Step 3: Create sample credentials
    create_test_credentials()
    
    # Step 4: Test components
    if env_ready:
        try:
            await test_components()
        except Exception as e:
            print(f"❌ Component testing failed: {e}")
    else:
        print("\n⚠️ Skipping component tests - configure .env file first")
    
    # Step 5: Usage instructions
    print("\n" + "=" * 60)
    print("📚 Usage Instructions:")
    print()
    print("1. Configure your environment:")
    print("   - Update .env with your Vertex AI project ID")
    print("   - Set path to your service account JSON file")
    print("   - Configure database connection details")
    print()
    print("2. Start the MCP server (in another terminal):")
    print("   cd ../mcp_server")
    print("   python sse_server.py")
    print()
    print("3. Start the MCP client:")
    print("   python client_sse.py")
    print("   # or")
    print("   python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload")
    print()
    print("4. Test the API:")
    print("   curl http://localhost:8080/health")
    print("   curl http://localhost:8080/documents")
    print()
    print("5. Access the API documentation:")
    print("   http://localhost:8080/docs")
    print()
    print("✅ Setup completed!")


if __name__ == "__main__":
    asyncio.run(main())