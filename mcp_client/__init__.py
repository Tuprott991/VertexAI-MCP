"""
Insurance MCP Client Package

Modular MCP client for insurance product inquiries with Vertex AI integration.
"""

from .config import settings
from .mcp_client import InsuranceMCPClient
from .vertex_ai_client import VertexAIClient
from .services import InsuranceService

__version__ = "2.0.0"
__all__ = [
    "settings",
    "InsuranceMCPClient", 
    "VertexAIClient",
    "InsuranceService"
]