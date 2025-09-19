#!/usr/bin/env python

"""
test_connection.py

Test script to verify MCP Client-Server connection and functionality
Run this script to test the insurance inquiry system end-to-end.
"""

import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_mcp_connection():
    """Test MCP client connection and tool functionality"""
    print("🧪 Testing MCP Client-Server Connection...")
    print("=" * 50)
    
    try:
        # Import the client
        from client_sse import InsuranceMCPClient
        
        # Create client instance
        client = InsuranceMCPClient("http://localhost:8081")
        
        # Test 1: Connection
        print("1️⃣ Testing connection to MCP server...")
        await client.connect()
        print("✅ Connected successfully!")
        print(f"Available tools: {client.available_tools}")
        
        # Test 2: List documents
        print("\n2️⃣ Testing document listing...")
        docs = await client.get_insurance_documents()
        print(f"✅ Found {len(docs)} documents:")
        for doc in docs[:3]:  # Show first 3
            print(f"   - {doc.get('name', 'Unknown')} ({doc.get('code', 'N/A')})")
        
        # Test 3: Get specific document
        print("\n3️⃣ Testing document content retrieval...")
        if docs:
            first_doc_code = docs[0].get('code')
            content = await client.get_document_content(first_doc_code)
            content_preview = content[:100] + "..." if len(content) > 100 else content
            print(f"✅ Retrieved content for '{first_doc_code}':")
            print(f"   Preview: {content_preview}")
        
        # Test 4: Chat history (empty thread)
        print("\n4️⃣ Testing chat history...")
        test_thread_id = f"test-{uuid.uuid4().hex[:8]}"
        history = await client.get_chat_history(test_thread_id)
        print(f"✅ Chat history for new thread: {history}")
        
        # Test 5: Insurance inquiry processing
        print("\n5️⃣ Testing insurance inquiry processing...")
        test_question = "Tôi muốn tìm hiểu về sản phẩm PruMax"
        result = await client.process_insurance_inquiry(
            thread_id=test_thread_id,
            user_id=1,
            question=test_question
        )
        print(f"✅ Processed inquiry successfully:")
        print(f"   Response: {result['response'][:150]}...")
        print(f"   Sources: {result['sources']}")
        
        # Test 6: Direct tool calling
        print("\n6️⃣ Testing direct tool calls...")
        try:
            cmd_result = await client.call_tool("run_command", {"command": "echo 'Hello from MCP!'"})
            print(f"✅ Command execution: {cmd_result.strip()}")
        except Exception as e:
            print(f"⚠️ Command tool test failed (expected if not available): {e}")
        
        await client.disconnect()
        print("\n🎉 All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        print(f"\n❌ Test failed: {e}")
        return False
    
    return True


async def test_api_endpoints():
    """Test FastAPI endpoints using httpx"""
    print("\n🌐 Testing FastAPI endpoints...")
    print("=" * 50)
    
    try:
        import httpx
        
        base_url = "http://localhost:8080"
        
        async with httpx.AsyncClient() as client:
            # Test health endpoint
            print("1️⃣ Testing health endpoint...")
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Health check: {health_data['status']}")
                print(f"   MCP connected: {health_data['mcp_connected']}")
            else:
                print(f"❌ Health check failed: {response.status_code}")
            
            # Test documents endpoint
            print("\n2️⃣ Testing documents endpoint...")
            response = await client.get(f"{base_url}/documents")
            if response.status_code == 200:
                docs_data = response.json()
                print(f"✅ Documents: {len(docs_data['documents'])} found")
            else:
                print(f"❌ Documents endpoint failed: {response.status_code}")
            
            # Test chat endpoint
            print("\n3️⃣ Testing chat endpoint...")
            chat_data = {
                "thread_id": f"test-api-{uuid.uuid4().hex[:8]}",
                "user_id": 1,
                "message": "Xin chào, tôi muốn tìm hiểu về bảo hiểm",
                "include_history": True
            }
            response = await client.post(f"{base_url}/chat", json=chat_data)
            if response.status_code == 200:
                chat_response = response.json()
                print(f"✅ Chat response received")
                print(f"   Thread: {chat_response['thread_id']}")
                print(f"   Response: {chat_response['response'][:100]}...")
            else:
                print(f"❌ Chat endpoint failed: {response.status_code}")
        
        print("\n🎉 API tests completed!")
        
    except ImportError:
        print("⚠️ httpx not available, skipping API tests")
    except Exception as e:
        print(f"❌ API test failed: {e}")


async def main():
    """Run all tests"""
    print("🚀 Insurance MCP System Test Suite")
    print("=" * 50)
    print("Make sure both MCP server (port 8081) and client (port 8080) are running!")
    print()
    
    # Test MCP connection
    mcp_success = await test_mcp_connection()
    
    # Test API endpoints
    if mcp_success:
        await asyncio.sleep(2)  # Give time for any cleanup
        await test_api_endpoints()
    
    print("\n" + "=" * 50)
    print("✅ Testing complete! Check the results above.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        sys.exit(1)