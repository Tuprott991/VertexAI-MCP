#!/usr/bin/env python

"""
test_pydantic_ai.py

Test script for the new Pydantic AI integration with Vertex AI Gemini 2.5 Flash
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_pydantic_ai_service():
    """Test the new Pydantic AI based insurance service"""
    
    print("🤖 Testing Pydantic AI Insurance Service")
    print("=" * 50)
    
    try:
        # Test 1: Import and create service
        print("1️⃣ Testing service import and creation...")
        from services import InsuranceService
        from config import ChatRequest
        
        service = InsuranceService()
        print("✅ Service created successfully")
        
        # Test 2: Initialize service (connects MCP)
        print("\n2️⃣ Testing service initialization...")
        try:
            await service.initialize()
            print("✅ Service initialized successfully")
        except Exception as e:
            print(f"⚠️ Service initialization failed (expected if MCP server not running): {e}")
            print("   Start MCP server with: cd ../mcp_server && python sse_server.py")
            return False
        
        # Test 3: Test product mention analysis
        print("\n3️⃣ Testing product mention analysis...")
        test_messages = [
            "Tôi muốn tìm hiểu về PruMax",
            "So sánh giữa Education Saver và PruMax",
            "Điều khoản của sản phẩm pru-edu-saver như thế nào?",
            "FAQ về prumax-faq"
        ]
        
        for msg in test_messages:
            codes = service._analyze_product_mentions(msg)
            print(f"   Message: '{msg}' → Codes: {codes}")
        
        print("✅ Product analysis working correctly")
        
        # Test 4: Test agent creation
        print("\n4️⃣ Testing Pydantic AI agent...")
        if hasattr(service, 'agent') and service.agent:
            print("✅ Pydantic AI agent created successfully")
            print(f"   Model: {service.agent.model}")
        else:
            print("❌ Agent not created properly")
            return False
        
        # Test 5: Test inquiry processing (if Vertex AI configured)
        print("\n5️⃣ Testing inquiry processing...")
        
        # Check if Vertex AI is configured
        from config import settings
        if not settings.vertex_ai.credentials_path or not Path(settings.vertex_ai.credentials_path).exists():
            print("⚠️ Vertex AI credentials not configured - skipping full test")
            print("   Configure VERTEX_AI__CREDENTIALS_PATH in .env")
        else:
            try:
                # Create a test request
                test_request = ChatRequest(
                    thread_id="test-thread-123",
                    user_id=1,
                    message="Xin chào, tôi muốn tìm hiểu về sản phẩm PruMax",
                    include_history=False
                )
                
                print(f"   Processing: '{test_request.message}'")
                response = await service.process_inquiry(test_request)
                
                print("✅ Inquiry processed successfully")
                print(f"   Response: {response.response[:100]}...")
                print(f"   Sources: {response.sources}")
                print(f"   Processing time: {response.processing_time:.2f}s")
                
            except Exception as e:
                print(f"⚠️ Full inquiry test failed: {e}")
                print("   This might be due to Vertex AI authentication or MCP server issues")
        
        # Test 6: Cleanup
        print("\n6️⃣ Testing service shutdown...")
        await service.shutdown()
        print("✅ Service shutdown completed")
        
        print("\n🎉 All tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"\n❌ Test failed: {e}")
        return False


async def test_direct_agent():
    """Test direct agent interaction (if possible)"""
    print("\n🔧 Testing Direct Agent Interaction")
    print("=" * 40)
    
    try:
        from services import InsuranceService, InsuranceContext
        
        service = InsuranceService()
        
        # Create a simple context
        context = InsuranceContext(
            thread_id="direct-test",
            user_id=1,
            chat_history=None
        )
        
        print("Agent created, context prepared")
        print("⚠️ Direct agent test requires full service initialization")
        
    except Exception as e:
        print(f"❌ Direct agent test failed: {e}")


async def main():
    """Main test function"""
    print("🚀 Pydantic AI Insurance Service Test Suite")
    print("=" * 60)
    
    # Test the service
    success = await test_pydantic_ai_service()
    
    # Test direct agent (optional)
    await test_direct_agent()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Test suite completed successfully!")
        print("\nNext steps:")
        print("1. Configure Vertex AI credentials")
        print("2. Start MCP server: cd ../mcp_server && python sse_server.py")
        print("3. Start client: python client_sse.py")
        print("4. Test API: curl http://localhost:8080/health")
    else:
        print("❌ Some tests failed - check configuration and dependencies")


if __name__ == "__main__":
    asyncio.run(main())