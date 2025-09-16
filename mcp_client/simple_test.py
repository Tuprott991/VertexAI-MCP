#!/usr/bin/env python

"""
Simple startup script to test the MCP client connection without FastAPI dependencies
"""

import asyncio
import sys
import os

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def simple_test():
    """Simple test without FastAPI dependencies"""
    print("🧪 Simple MCP Client Test")
    print("=" * 30)
    
    try:
        # Test basic imports
        print("1️⃣ Testing imports...")
        from mcp.client.session import ClientSession
        from mcp.client.sse import SseClientTransport
        print("✅ MCP imports successful")
        
        # Test server connection
        print("\n2️⃣ Testing server connection...")
        server_url = "http://localhost:8081"
        transport = SseClientTransport(f"{server_url}/sse")
        session = ClientSession(transport)
        
        print(f"   Connecting to: {server_url}")
        await session.initialize()
        print("✅ Connected to MCP server!")
        
        # List tools
        print("\n3️⃣ Listing available tools...")
        from mcp.types import ListToolsRequest
        result = await session.list_tools(ListToolsRequest())
        tools = [tool.name for tool in result.tools]
        print(f"✅ Available tools: {tools}")
        
        # Test a simple tool call
        print("\n4️⃣ Testing tool call...")
        if "list_documents" in tools:
            from mcp.types import CallToolRequest
            request = CallToolRequest(name="list_documents", arguments={})
            result = await session.call_tool(request)
            if result.content:
                print(f"✅ Tool call successful!")
                print(f"   Result preview: {str(result.content[0])[:100]}...")
        
        await session.close()
        await transport.close()
        
        print("\n🎉 Simple test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(simple_test())
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)