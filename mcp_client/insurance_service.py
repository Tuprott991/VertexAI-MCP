"""
insurance_service.py

Insurance-specific business logic service layer.
Handles conversation processing, product inquiries, and chat history integration.
"""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from .config import settings, ChatRequest, ChatResponse, DocumentInfo
from .mcp_client import InsuranceMCPClient, MCPConnectionError, MCPToolError
from .vertex_ai_client import VertexAIClient, VertexAIError

# Import database functions
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.chat_history import save_chat_history

logger = logging.getLogger(__name__)


class InsuranceServiceError(Exception):
    """Base exception for insurance service operations"""
    pass


class InsuranceService:
    """
    Insurance conversation and inquiry processing service.
    
    Combines MCP client (for tools and data) with Vertex AI (for intelligent responses)
    to provide comprehensive insurance assistance.
    """
    
    def __init__(self):
        self.mcp_client = InsuranceMCPClient()
        self.vertex_ai_client = VertexAIClient()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all service components"""
        if self._initialized:
            return
        
        try:
            # Initialize MCP client
            await self.mcp_client.connect()
            
            # Initialize Vertex AI client
            await self.vertex_ai_client.initialize()
            
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
        Process an insurance inquiry with full context and intelligent response.
        
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
            # Step 1: Gather conversation context
            context_info = await self._gather_context(request.thread_id, request.include_history, request.max_history)
            
            # Step 2: Analyze message for product mentions and intent
            product_analysis = self._analyze_product_mentions(request.message)
            
            # Step 3: Retrieve relevant documents
            documents_info = await self._retrieve_relevant_documents(request.message, product_analysis)
            
            # Step 4: Generate intelligent response using Vertex AI
            response_text, ai_metadata = await self._generate_ai_response(
                user_message=request.message,
                thread_id=request.thread_id,
                chat_history=context_info.get("history_text"),
                relevant_documents=documents_info["contents"],
                sources_used=documents_info["sources"]
            )
            
            # Step 5: Create response object
            processing_time = (datetime.now() - start_time).total_seconds()
            
            response = ChatResponse(
                thread_id=request.thread_id,
                response=response_text,
                sources=documents_info["sources"],
                timestamp=datetime.now(),
                tokens_used=ai_metadata.get("total_tokens"),
                processing_time=processing_time
            )
            
            # Step 6: Save to database asynchronously
            asyncio.create_task(self._save_conversation(request, response))
            
            logger.info(f"Inquiry processed successfully in {processing_time:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"Failed to process inquiry: {e}")
            # Return error response
            return ChatResponse(
                thread_id=request.thread_id,
                response=f"Xin lỗi, đã có lỗi xảy ra khi xử lý câu hỏi của bạn. Vui lòng thử lại sau. Lỗi: {str(e)}",
                sources=[],
                timestamp=datetime.now(),
                processing_time=(datetime.now() - start_time).total_seconds()
            )
    
    async def _gather_context(self, thread_id: str, include_history: bool, max_history: int) -> Dict[str, Any]:
        """Gather conversation context including chat history"""
        context = {"history_text": None, "history_messages": []}
        
        if include_history and thread_id:
            try:
                history_text = await self.mcp_client.get_chat_history(thread_id, max_history)
                if history_text:
                    context["history_text"] = history_text
                    # Parse history into messages if needed
                    context["history_messages"] = self._parse_history_text(history_text)
            except Exception as e:
                logger.warning(f"Failed to retrieve chat history for {thread_id}: {e}")
        
        return context
    
    def _analyze_product_mentions(self, message: str) -> Dict[str, Any]:
        """
        Analyze message for product mentions and intent.
        
        Args:
            message: User message to analyze
            
        Returns:
            Dictionary with product analysis results
        """
        analysis = {
            "mentioned_products": [],
            "product_codes": [],
            "intent": "general",
            "keywords": []
        }
        
        if not settings.insurance or not settings.insurance.product_codes:
            return analysis
        
        message_lower = message.lower()
        
        # Check for product mentions
        for product_family, codes in settings.insurance.product_codes.items():
            family_lower = product_family.lower()
            
            # Check family name mentions
            if family_lower in message_lower:
                analysis["mentioned_products"].append(product_family)
                analysis["product_codes"].extend(codes.values())
            
            # Check specific code mentions
            for code_type, code in codes.items():
                if code.lower() in message_lower:
                    analysis["mentioned_products"].append(f"{product_family}_{code_type}")
                    analysis["product_codes"].append(code)
        
        # Analyze intent
        intent_keywords = {
            "comparison": ["so sánh", "khác biệt", "compare", "difference", "versus", "vs"],
            "information": ["thông tin", "tìm hiểu", "information", "details", "giới thiệu"],
            "terms": ["điều kiện", "điều khoản", "terms", "conditions", "quy định"],
            "faq": ["hỏi đáp", "faq", "câu hỏi", "questions"],
            "pricing": ["giá", "phí", "price", "cost", "chi phí", "pricing"]
        }
        
        for intent_type, keywords in intent_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                analysis["intent"] = intent_type
                analysis["keywords"].extend([kw for kw in keywords if kw in message_lower])
                break
        
        return analysis
    
    async def _retrieve_relevant_documents(self, message: str, product_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve relevant documents based on message analysis.
        
        Args:
            message: User message
            product_analysis: Product analysis results
            
        Returns:
            Dictionary with document contents and sources
        """
        documents_info = {
            "contents": [],
            "sources": [],
            "available_products": []
        }
        
        try:
            # Get available documents
            available_docs = await self.mcp_client.get_documents_list()
            documents_info["available_products"] = available_docs
            
            # If specific products mentioned, get their content
            if product_analysis["product_codes"]:
                for product_code in product_analysis["product_codes"][:3]:  # Limit to 3 documents
                    content = await self.mcp_client.get_document_content(product_code)
                    if content:
                        documents_info["contents"].append(content)
                        documents_info["sources"].append(product_code)
            
            # If no specific products mentioned but asking about products/comparison
            elif product_analysis["intent"] in ["information", "comparison"] and any(
                keyword in message.lower() for keyword in ["sản phẩm", "product", "bảo hiểm", "insurance"]
            ):
                # Get first few available documents as context
                for doc in available_docs[:2]:
                    if doc.get("code"):
                        content = await self.mcp_client.get_document_content(doc["code"])
                        if content:
                            documents_info["contents"].append(content)
                            documents_info["sources"].append(doc["code"])
            
        except Exception as e:
            logger.error(f"Failed to retrieve documents: {e}")
        
        return documents_info
    
    async def _generate_ai_response(
        self,
        user_message: str,
        thread_id: str,
        chat_history: Optional[str] = None,
        relevant_documents: List[str] = None,
        sources_used: List[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate AI response using Vertex AI"""
        try:
            return await self.vertex_ai_client.generate_insurance_response(
                user_message=user_message,
                thread_id=thread_id,
                chat_history=chat_history,
                relevant_documents=relevant_documents,
                sources_used=sources_used
            )
        except VertexAIError as e:
            logger.error(f"Vertex AI generation failed: {e}")
            # Fallback to basic response
            return self._generate_fallback_response(user_message, relevant_documents, sources_used), {}
    
    def _generate_fallback_response(
        self,
        user_message: str,
        relevant_documents: List[str] = None,
        sources_used: List[str] = None
    ) -> str:
        """Generate fallback response when AI is unavailable"""
        if not relevant_documents:
            return ("Tôi đã nhận được câu hỏi của bạn về bảo hiểm. "
                   "Hiện tại hệ thống AI đang gặp sự cố tạm thời. "
                   "Vui lòng thử lại sau hoặc liên hệ với chúng tôi để được hỗ trợ trực tiếp.")
        
        response_parts = ["Dựa trên thông tin sản phẩm có sẵn:"]
        
        for i, doc_content in enumerate(relevant_documents[:2]):
            source = sources_used[i] if sources_used and i < len(sources_used) else f"Tài liệu {i+1}"
            preview = doc_content[:300] + "..." if len(doc_content) > 300 else doc_content
            response_parts.append(f"\n• {source}: {preview}")
        
        if sources_used:
            response_parts.append(f"\nNguồn thông tin: {', '.join(sources_used)}")
        
        response_parts.append("\nVui lòng thử lại sau để nhận được phản hồi chi tiết hơn từ AI.")
        
        return "\n".join(response_parts)
    
    def _parse_history_text(self, history_text: str) -> List[Dict[str, Any]]:
        """Parse formatted history text into message objects"""
        messages = []
        # This is a simple parser - could be enhanced based on actual format
        lines = history_text.split('\n')
        current_message = None
        
        for line in lines:
            line = line.strip()
            if line.startswith('User:') or line.startswith('Question:'):
                if current_message:
                    messages.append(current_message)
                current_message = {"role": "user", "content": line[line.find(':')+1:].strip()}
            elif line.startswith('Assistant:') or line.startswith('Answer:'):
                if current_message:
                    messages.append(current_message)
                current_message = {"role": "assistant", "content": line[line.find(':')+1:].strip()}
            elif current_message and line:
                current_message["content"] += " " + line
        
        if current_message:
            messages.append(current_message)
        
        return messages
    
    async def _save_conversation(self, request: ChatRequest, response: ChatResponse) -> None:
        """Save conversation to database"""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                save_chat_history,
                request.user_id,
                request.thread_id,
                request.message,
                response.response
            )
            logger.debug(f"Conversation saved for thread {request.thread_id}")
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
    
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