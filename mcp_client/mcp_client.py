"""
mcp_client.py

Core MCP client implementation for connecting to the insurance MCP server via SSE.
Handles tool discovery, calling, and connection management.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from mcp.client.session import ClientSession
from mcp.client.sse import SseClientTransport
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    TextContent
)

from .config import settings

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """Base exception for MCP client errors"""
    pass


class MCPConnectionError(MCPClientError):
    """Raised when MCP connection fails"""
    pass


class MCPToolError(MCPClientError):
    """Raised when MCP tool execution fails"""
    pass


class MCPClient:
    """
    Core MCP client for connecting to insurance MCP server via SSE.
    
    Provides:
    - Connection management with retry logic
    - Tool discovery and execution
    - Error handling and logging
    - Context manager support
    """
    
    def __init__(self):
        self.server_url = settings.mcp.server_url
        self.session: Optional[ClientSession] = None
        self.transport: Optional[SseClientTransport] = None
        self.available_tools: List[str] = []
        self._connected = False
        self._connection_lock = asyncio.Lock()
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected to MCP server"""
        return self._connected and self.session is not None
    
    async def connect(self) -> None:
        """
        Establish connection to MCP server with retry logic.
        
        Raises:
            MCPConnectionError: If connection fails after all retries
        """
        async with self._connection_lock:
            if self.is_connected:
                return
            
            for attempt in range(settings.mcp.retry_attempts):
                try:
                    await self._attempt_connection()
                    self._connected = True
                    logger.info(f"Connected to MCP server at {self.server_url}")
                    logger.info(f"Available tools: {self.available_tools}")
                    return
                    
                except Exception as e:
                    logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                    if attempt < settings.mcp.retry_attempts - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        raise MCPConnectionError(f"Failed to connect after {settings.mcp.retry_attempts} attempts: {e}")
    
    async def _attempt_connection(self) -> None:
        """Single connection attempt"""
        # Create SSE transport
        sse_url = f"{self.server_url}/sse"
        self.transport = SseClientTransport(sse_url)
        
        # Create client session with timeout
        self.session = ClientSession(self.transport)
        
        # Initialize connection
        await asyncio.wait_for(
            self.session.initialize(),
            timeout=settings.mcp.connection_timeout
        )
        
        # Discover available tools
        await self._refresh_tools()
    
    async def disconnect(self) -> None:
        """Close connection to MCP server"""
        async with self._connection_lock:
            if self.session:
                try:
                    await self.session.close()
                except Exception as e:
                    logger.warning(f"Error closing session: {e}")
                finally:
                    self.session = None
            
            if self.transport:
                try:
                    await self.transport.close()
                except Exception as e:
                    logger.warning(f"Error closing transport: {e}")
                finally:
                    self.transport = None
            
            self._connected = False
            self.available_tools = []
            logger.info("Disconnected from MCP server")
    
    async def _refresh_tools(self) -> None:
        """Discover available tools from MCP server"""
        if not self.session:
            raise MCPConnectionError("Not connected to MCP server")
        
        try:
            result = await self.session.list_tools(ListToolsRequest())
            self.available_tools = [tool.name for tool in result.tools]
            logger.debug(f"Discovered {len(self.available_tools)} tools: {self.available_tools}")
        except Exception as e:
            logger.error(f"Failed to refresh tools: {e}")
            raise MCPToolError(f"Tool discovery failed: {e}")
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments as dictionary
            
        Returns:
            Tool execution result
            
        Raises:
            MCPConnectionError: If not connected to server
            MCPToolError: If tool execution fails
        """
        if not self.is_connected:
            raise MCPConnectionError("Not connected to MCP server")
        
        if tool_name not in self.available_tools:
            available = ", ".join(self.available_tools)
            raise MCPToolError(f"Tool '{tool_name}' not available. Available tools: {available}")
        
        try:
            request = CallToolRequest(
                name=tool_name,
                arguments=arguments
            )
            
            logger.debug(f"Calling tool '{tool_name}' with arguments: {arguments}")
            result = await self.session.call_tool(request)
            
            # Extract content from result
            if result.content:
                if isinstance(result.content[0], TextContent):
                    return result.content[0].text
                else:
                    return str(result.content[0])
            
            return None
            
        except Exception as e:
            logger.error(f"Tool '{tool_name}' execution failed: {e}")
            raise MCPToolError(f"Tool execution failed: {e}")
    
    async def call_tool_safe(self, tool_name: str, arguments: Dict[str, Any]) -> tuple[bool, Any, Optional[str]]:
        """
        Safe tool calling that returns success status instead of raising exceptions.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments as dictionary
            
        Returns:
            Tuple of (success, result, error_message)
        """
        try:
            result = await self.call_tool(tool_name, arguments)
            return True, result, None
        except Exception as e:
            return False, None, str(e)
    
    async def ensure_connected(self) -> None:
        """Ensure connection is established, reconnect if necessary"""
        if not self.is_connected:
            await self.connect()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on MCP connection.
        
        Returns:
            Dictionary with health status information
        """
        health_info = {
            "connected": self.is_connected,
            "server_url": self.server_url,
            "available_tools": self.available_tools,
            "tool_count": len(self.available_tools)
        }
        
        if self.is_connected:
            # Test a simple tool call if available
            try:
                if "list_documents" in self.available_tools:
                    success, _, error = await self.call_tool_safe("list_documents", {})
                    health_info["test_tool_call"] = success
                    health_info["test_error"] = error
                else:
                    health_info["test_tool_call"] = None
                    health_info["test_error"] = "No test tool available"
            except Exception as e:
                health_info["test_tool_call"] = False
                health_info["test_error"] = str(e)
        
        return health_info


# Specialized tool calling methods for insurance domain
class InsuranceMCPClient(MCPClient):
    """
    Insurance-specific MCP client with domain-specific tool calling methods.
    """
    
    async def get_documents_list(self) -> List[Dict[str, Any]]:
        """
        Get list of available insurance documents.
        
        Returns:
            List of document dictionaries with code, name, etc.
        """
        try:
            result = await self.call_tool("list_documents", {})
            if result:
                # Parse the string result back to list
                import ast
                return ast.literal_eval(result) if result else []
            return []
        except Exception as e:
            logger.error(f"Failed to get documents list: {e}")
            return []
    
    async def get_document_content(self, product_code: str) -> Optional[str]:
        """
        Get content of specific insurance document.
        
        Args:
            product_code: Insurance product code
            
        Returns:
            Document content or None if not found
        """
        try:
            result = await self.call_tool("get_document_content", {"code": product_code})
            if result and "not found" not in result.lower() and "error" not in result.lower():
                return result
            return None
        except Exception as e:
            logger.error(f"Failed to get document content for '{product_code}': {e}")
            return None
    
    async def get_chat_history(self, thread_id: str, limit: int = 10) -> Optional[str]:
        """
        Get formatted chat history for a thread.
        
        Args:
            thread_id: Chat thread identifier
            limit: Maximum number of messages to retrieve
            
        Returns:
            Formatted chat history or None if not found
        """
        try:
            result = await self.call_tool("get_chat_history", {
                "thread_id": thread_id,
                "limit": limit
            })
            if result and "No chat history found" not in result:
                return result
            return None
        except Exception as e:
            logger.error(f"Failed to get chat history for thread '{thread_id}': {e}")
            return None
    
    async def execute_command(self, command: str) -> Optional[str]:
        """
        Execute a system command via MCP server (if available).
        
        Args:
            command: Command to execute
            
        Returns:
            Command output or None if failed
        """
        try:
            if "run_command" in self.available_tools:
                result = await self.call_tool("run_command", {"command": command})
                return result
            else:
                logger.warning("Command execution tool not available")
                return None
        except Exception as e:
            logger.error(f"Failed to execute command '{command}': {e}")
            return None