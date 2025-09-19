"""
services.py

Insurance service layer using Pydantic AI with Vertex AI Gemini 2.5 Flash.
Implements agent-based document retrieval and direct database integration.
"""

import asyncio
import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple, Annotated
from datetime import datetime
from pathlib import Path

from google.oauth2 import service_account
# Google AI safety settings will use string constants

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.providers.google import GoogleProvider
from pydantic import BaseModel, Field

from .config import settings, ChatRequest, ChatResponse, DocumentInfo
from .mcp_client import InsuranceMCPClient, MCPConnectionError, MCPToolError

# Import database functions directly
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.chat_history import save_chat_history, get_recent_chat_history, format_chat_history

logger = logging.getLogger(__name__)


class InsuranceServiceError(Exception):
    """Base exception for insurance service operations"""
    pass


class InsuranceContext(BaseModel):
    """Context passed to the Pydantic AI agent"""
    thread_id: str
    user_id: int
    chat_history: Optional[str] = None
    mcp_client: Optional[object] = Field(None, exclude=True)  # Exclude from serialization


class InsuranceService:
    """
    Insurance conversation service using Pydantic AI agent with Vertex AI Gemini 2.5 Flash.
    
    Features:
    - Pydantic AI agent with MCP tools integration
    - Direct database access for chat history
    - Agent-based document retrieval decisions
    - Vertex AI Gemini 2.5 Flash as core LLM
    """
    
    # Shared model and provider (expensive to create, safe to share)
    _model_instance = None
    _provider_instance = None
    _model_lock = asyncio.Lock()
    
    def __init__(self):
        self.mcp_client = InsuranceMCPClient()
        self._initialized = False
    
    @classmethod
    async def get_shared_model(cls):
        """Get or create shared model and provider instances"""
        if cls._model_instance is None:
            async with cls._model_lock:
                if cls._model_instance is None:
                    cls._provider_instance, cls._model_instance = cls._create_shared_model()
        return cls._provider_instance, cls._model_instance
    
    async def create_agent(self) -> Agent[InsuranceContext, str]:
        """Create a new agent instance for each request (thread-safe)"""
        provider, model = await self.get_shared_model()
        return self._create_agent_with_model(model)
    
    @classmethod
    def _create_shared_model(cls):
        """Create shared model and provider instances (expensive, created once)"""
        
        # Setup service account credentials
        if not settings.vertex_ai.credentials_path:
            raise InsuranceServiceError("Vertex AI credentials path not configured")
        
        try:
            credentials = service_account.Credentials.from_service_account_file(
                settings.vertex_ai.credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform'],
            )
        except Exception as e:
            raise InsuranceServiceError(f"Failed to load service account credentials: {e}")
        
        # Create provider and model (these are expensive to create, safe to share)
        provider = GoogleProvider(
            credentials=credentials, 
            project=settings.vertex_ai.project_id
        )
        
        model = GoogleModel(
            settings.vertex_ai.model_name or 'gemini-2.5-flash',
            provider=provider
        )
        
        return provider, model
    
    def _create_agent_with_model(self, model) -> Agent[InsuranceContext, str]:
        """Create a new agent instance using shared model (lightweight, per-request)"""
        
        # Configure model settings
        model_settings = GoogleModelSettings(
            temperature=settings.vertex_ai.temperature,
            max_tokens=settings.vertex_ai.max_tokens,
            google_thinking_config={'thinking_budget': 2048},
            google_safety_settings=[
                {
                    'category': 'HARM_CATEGORY_HATE_SPEECH',
                    'threshold': 'BLOCK_LOW_AND_ABOVE',
                },
                {
                    'category': 'HARM_CATEGORY_DANGEROUS_CONTENT',
                    'threshold': 'BLOCK_LOW_AND_ABOVE',
                },
                {
                    'category': 'HARM_CATEGORY_HARASSMENT',
                    'threshold': 'BLOCK_LOW_AND_ABOVE',
                },
                {
                    'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT',
                    'threshold': 'BLOCK_MEDIUM_AND_ABOVE',
                }
            ]
        )
        
        # Load system prompt from prompt.json
        system_prompt = self._load_system_prompt()
        
        # Create agent (lightweight, per-request)
        agent = Agent(
            model=model,
            model_settings=model_settings,
            system_prompt=system_prompt,
            result_type=str
        )
        
        # Register MCP tools
        self._register_agent_tools(agent)
        
        return agent
    
    @classmethod
    def _load_system_prompt(cls) -> str:
        """Load system prompt from prompt.json file"""
        try:
            prompt_file = Path(__file__).parent / "prompt.json"
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompt_data = json.load(f)
                    return prompt_data.get('system_prompt', cls._get_default_system_prompt())
            else:
                logger.warning("prompt.json not found, using default system prompt")
                return cls._get_default_system_prompt()
        except Exception as e:
            logger.error(f"Error loading system prompt from prompt.json: {e}")
            return cls._get_default_system_prompt()
    
    @classmethod
    def _get_default_system_prompt(cls) -> str:
        """Default system prompt if prompt.json is not available"""
        return (
            "You are an intelligent insurance assistant. Use the available tools to help customers "
            "with insurance product inquiries. Always retrieve relevant documents when discussing "
            "specific products and provide accurate, helpful information."
        )
    
    def _register_agent_tools(self, agent: Agent) -> None:
        """Register MCP tools as agent functions"""
        
        @agent.tool
        async def list_documents(ctx: RunContext[InsuranceContext]) -> str:
            """Get list of all available insurance documents with their codes and names."""
            try:
                if not ctx.deps.mcp_client:
                    return "MCP client not available"
                
                result = await ctx.deps.mcp_client.call_tool("list_documents", {})
                return result or "No documents found"
            except Exception as e:
                logger.error(f"Error listing documents: {e}")
                return f"Error retrieving documents: {str(e)}"
        
        @agent.tool
        async def get_document_content(
            ctx: RunContext[InsuranceContext], 
            code: Annotated[str, "Insurance product code (e.g., 'pru-edu-saver', 'prumax', 'prumax-faq')"]
        ) -> str:
            """Get detailed content of a specific insurance document by its code."""
            try:
                if not ctx.deps.mcp_client:
                    return "MCP client not available"
                
                result = await ctx.deps.mcp_client.call_tool("get_document_content", {"code": code})
                return result or f"Document with code '{code}' not found"
            except Exception as e:
                logger.error(f"Error getting document content for {code}: {e}")
                return f"Error retrieving document '{code}': {str(e)}"
        
        # @agent.tool
        # async def get_chat_history(
        #     ctx: RunContext[InsuranceContext],
        #     limit: Annotated[int, "Maximum number of messages to retrieve"] = 10
        # ) -> str:
        #     """Get recent chat history for the current conversation thread."""
        #     try:
        #         if not ctx.deps.thread_id:
        #             return "No conversation thread available"
                
        #         # Use direct database function instead of MCP tool
        #         history = get_recent_chat_history(ctx.deps.thread_id, limit)
        #         if history:
        #             return format_chat_history(history)
        #         else:
        #             return "No chat history found for this conversation"
        #     except Exception as e:
        #         logger.error(f"Error getting chat history: {e}")
        #         return f"Error retrieving chat history: {str(e)}"
        
        @agent.tool
        async def run_command(
            ctx: RunContext[InsuranceContext],
            command: Annotated[str, "System command to execute"]
        ) -> str:
            """Execute a system command (use with caution)."""
            try:
                if not ctx.deps.mcp_client:
                    return "MCP client not available"
                
                result = await ctx.deps.mcp_client.call_tool("run_command", {"command": command})
                return result or "Command executed with no output"
            except Exception as e:
                logger.error(f"Error executing command: {e}")
                return f"Error executing command: {str(e)}"
    
    # def _analyze_product_mentions(self, message: str) -> List[str]:
    #     """
    #     Analyze message for product mentions and return likely product codes.
    #     COMMENTED OUT: The reasoning agent can analyze and decide which documents 
    #     to retrieve on its own, making this pre-analysis unnecessary.
    #     """
    #     if not settings.insurance or not settings.insurance.product_codes:
    #         return []
    #     
    #     message_lower = message.lower()
    #     mentioned_codes = []
    #     
    #     # Check for product family mentions
    #     for product_family, codes in settings.insurance.product_codes.items():
    #         family_lower = product_family.lower()
    #         
    #         # Check if family name is mentioned
    #         if family_lower in message_lower or any(word in message_lower for word in family_lower.split('_')):
    #             # Determine which document type based on intent
    #             if any(term in message_lower for term in ['faq', 'hỏi đáp', 'câu hỏi', 'questions']):
    #                 mentioned_codes.append(codes.get('faq', codes.get('main')))
    #             elif any(term in message_lower for term in ['điều kiện', 'điều khoản', 'terms', 'conditions']):
    #                 mentioned_codes.append(codes.get('terms', codes.get('main')))
    #             else:
    #                 mentioned_codes.append(codes.get('main'))
    #         
    #         # Check for specific code mentions
    #         for code_type, code in codes.items():
    #             if code.lower() in message_lower:
    #                 mentioned_codes.append(code)
    #     
    #     # Remove duplicates while preserving order
    #     return list(dict.fromkeys(filter(None, mentioned_codes)))
    
    async def initialize(self) -> None:
        """Initialize all service components"""
        if self._initialized:
            return
        
        try:
            # Initialize MCP client
            await self.mcp_client.connect()
            
            self._initialized = True
            logger.info("Insurance service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize insurance service: {e}")
            raise InsuranceServiceError(f"Service initialization failed: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown service and cleanup resources"""
        try:
            await self.mcp_client.disconnect()
            logger.info("Insurance service shutdown completed")
        except Exception as e:
            logger.error(f"Error during service shutdown: {e}")
    
    async def process_inquiry(self, request: ChatRequest) -> ChatResponse:
        """
        Process an insurance inquiry using Pydantic AI agent with MCP tools.
        
        Args:
            request: Chat request with user message and context
            
        Returns:
            Chat response with AI-generated answer and sources
            
        Raises:
            InsuranceServiceError: If processing fails
        """
        if not self._initialized:
            await self.initialize()
        
        start_time = datetime.now()
        
        try:
            # Step 1: Get chat history directly from database
            chat_history = None
            if request.include_history and request.thread_id:
                try:
                    history = get_recent_chat_history(request.thread_id, request.max_history)
                    if history:
                        chat_history = format_chat_history(history)
                        logger.debug(f"Retrieved chat history for thread {request.thread_id}")
                except Exception as e:
                    logger.warning(f"Failed to get chat history: {e}")
            
            # Step 2: Skip product mention analysis - let the reasoning agent decide
            # mentioned_codes = self._analyze_product_mentions(request.message)
            # logger.debug(f"Analyzed product mentions: {mentioned_codes}")
            mentioned_codes = []  # Empty list - let agent reason about which documents to use
            
            # Step 3: Create context for the agent
            context = InsuranceContext(
                thread_id=request.thread_id,
                user_id=request.user_id,
                chat_history=chat_history,
                mcp_client=self.mcp_client
            )
            
            # Step 4: Enhanced user message with context hints
            enhanced_message = self._enhance_message_with_context(
                request.message, 
                mentioned_codes, 
                chat_history
            )
            
            # Step 5: Create a fresh agent and run it to generate response with tools
            logger.info(f"Processing inquiry with Pydantic AI agent for thread {request.thread_id}")
            agent = await self.create_agent()
            result = await agent.run(enhanced_message, deps=context)
            
            # Step 6: Extract response and metadata  
            response_text = result.data if hasattr(result, 'data') else str(result)
            
            # Extract sources from tool usage (if available in result)
            sources_used = self._extract_sources_from_result(result, mentioned_codes)
            
            # Step 7: Create response object
            processing_time = (datetime.now() - start_time).total_seconds()
            
            response = ChatResponse(
                thread_id=request.thread_id,
                response=response_text,
                sources=sources_used,
                timestamp=datetime.now(),
                tokens_used=getattr(result, 'usage', {}).get('total_tokens'),
                processing_time=processing_time
            )
            
            # Step 8: Save conversation to database
            try:
                save_chat_history(
                    # request.user_id,
                    request.thread_id,
                    request.message,
                    response_text
                )
                logger.debug(f"Saved conversation for thread {request.thread_id}")
            except Exception as e:
                logger.error(f"Failed to save conversation: {e}")
            
            logger.info(f"Inquiry processed successfully in {processing_time:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"Failed to process inquiry: {e}")
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Return error response
            return ChatResponse(
                thread_id=request.thread_id,
                response=f"Xin lỗi, đã có lỗi xảy ra khi xử lý câu hỏi của bạn. Vui lòng thử lại sau.",
                sources=[],
                timestamp=datetime.now(),
                processing_time=processing_time
            )
    
    def _enhance_message_with_context(
        self, 
        message: str, 
        mentioned_codes: List[str], 
        chat_history: Optional[str]
    ) -> str:
        """
        Enhance user message with context hints for the agent.
        Since we're using a reasoning agent, we let it decide which documents to retrieve.
        """
        enhanced_parts = []
        
        # Add chat history context if available
        if chat_history:
            enhanced_parts.append(f"[CONTEXT] Previous conversation:\n{chat_history}\n")
        
        # Let the reasoning agent decide which documents to retrieve
        # No need to pre-analyze product mentions - the agent can reason about this
        
        # Add the actual user message
        enhanced_parts.append(f"[USER MESSAGE] {message}")
        
        return "\n".join(enhanced_parts)
    
    def _extract_sources_from_result(self, result, mentioned_codes: List[str]) -> List[str]:
        """
        Extract document sources used during agent execution.
        This is a simplified version - in practice, you might track tool calls.
        """
        sources = []
        
        # If we have tool call information in result, extract it
        if hasattr(result, 'tool_calls') or hasattr(result, 'calls'):
            tool_calls = getattr(result, 'tool_calls', getattr(result, 'calls', []))
            for call in tool_calls:
                if hasattr(call, 'tool_name') and call.tool_name == 'get_document_content':
                    if hasattr(call, 'arguments') and 'code' in call.arguments:
                        sources.append(call.arguments['code'])
        
        # Fallback: use mentioned codes as potential sources
        if not sources and mentioned_codes:
            sources = mentioned_codes[:3]  # Limit to 3 sources
        
        return sources
    
    async def get_documents(self) -> List[DocumentInfo]:
        """Get list of available insurance documents"""
        if not self._initialized:
            await self.initialize()
        
        try:
            docs = await self.mcp_client.get_documents_list()
            return [
                DocumentInfo(
                    code=doc.get("code", ""),
                    name=doc.get("name", "Unknown"),
                    created_at=doc.get("created_at")
                )
                for doc in docs
            ]
        except Exception as e:
            logger.error(f"Failed to get documents: {e}")
            return []
    
    async def get_document_content(self, product_code: str) -> Optional[str]:
        """Get content of specific document"""
        if not self._initialized:
            await self.initialize()
        
        try:
            return await self.mcp_client.get_document_content(product_code)
        except Exception as e:
            logger.error(f"Failed to get document content: {e}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        health_info = {
            "service_initialized": self._initialized,
            "timestamp": datetime.now().isoformat()
        }
        
        if self._initialized:
            try:
                # Check MCP client
                mcp_health = await self.mcp_client.health_check()
                health_info["mcp_client"] = mcp_health
                
                # Check Vertex AI client
                vertex_health = await self.vertex_ai_client.health_check()
                health_info["vertex_ai"] = vertex_health
                
                # Overall status
                health_info["overall_status"] = (
                    "healthy" if mcp_health.get("connected") and vertex_health.get("initialized")
                    else "degraded"
                )
                
            except Exception as e:
                health_info["error"] = str(e)
                health_info["overall_status"] = "unhealthy"
        else:
            health_info["overall_status"] = "not_initialized"
        
        return health_info