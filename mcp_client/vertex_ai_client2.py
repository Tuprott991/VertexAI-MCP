"""
vertex_ai_client.py

Vertex AI Gemini integration for the Insurance MCP Client.
Handles authentication, conversation processing, and response generation.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

import vertexai
from vertexai.generative_models import GenerativeModel, Part, Content
from google.auth import default
from google.auth.exceptions import DefaultCredentialsError

from .config import settings, ChatMessage

logger = logging.getLogger(__name__)


class VertexAIError(Exception):
    """Base exception for Vertex AI operations"""
    pass


class VertexAIAuthError(VertexAIError):
    """Raised when Vertex AI authentication fails"""
    pass


class VertexAIGenerationError(VertexAIError):
    """Raised when text generation fails"""
    pass


class VertexAIClient:
    """
    Vertex AI Gemini client for insurance conversation processing.
    
    Features:
    - IAM-based authentication with service account JSON
    - Gemini 2.0 Flash integration
    - Conversation context management
    - Token usage tracking
    - Error handling and retries
    """
    
    def __init__(self):
        self.project_id = settings.vertex_ai.project_id
        self.location = settings.vertex_ai.location
        self.model_name = settings.vertex_ai.model_name
        self.model: Optional[GenerativeModel] = None
        self._initialized = False
        
        # Generation parameters
        self.generation_config = {
            "max_output_tokens": settings.vertex_ai.max_tokens,
            "temperature": settings.vertex_ai.temperature,
            "top_p": settings.vertex_ai.top_p,
            "top_k": settings.vertex_ai.top_k,
        }
    
    async def initialize(self) -> None:
        """
        Initialize Vertex AI client with authentication.
        
        Raises:
            VertexAIAuthError: If authentication fails
            VertexAIError: If initialization fails
        """
        if self._initialized:
            return
        
        try:
            # Initialize Vertex AI
            vertexai.init(project=self.project_id, location=self.location)
            
            # Test credentials
            await self._test_credentials()
            
            # Initialize model
            self.model = GenerativeModel(
                model_name=self.model_name,
                generation_config=self.generation_config
            )
            
            self._initialized = True
            logger.info(f"Vertex AI initialized: {self.model_name} in {self.project_id}/{self.location}")
            
        except DefaultCredentialsError as e:
            raise VertexAIAuthError(f"Authentication failed: {e}")
        except Exception as e:
            raise VertexAIError(f"Vertex AI initialization failed: {e}")
    
    async def _test_credentials(self) -> None:
        """Test if credentials are valid"""
        try:
            # This will raise an exception if credentials are invalid
            credentials, project = default()
            if not credentials:
                raise VertexAIAuthError("No valid credentials found")
            logger.debug("Vertex AI credentials validated successfully")
        except Exception as e:
            raise VertexAIAuthError(f"Credential validation failed: {e}")
    
    def _prepare_conversation_context(
        self,
        system_prompt: str,
        chat_history: Optional[str] = None,
        documents_context: Optional[str] = None,
        user_message: str = ""
    ) -> List[Content]:
        """
        Prepare conversation context for Gemini.
        
        Args:
            system_prompt: System instruction for the assistant
            chat_history: Previous conversation history
            documents_context: Relevant document information
            user_message: Current user message
            
        Returns:
            List of Content objects for Gemini
        """
        contents = []
        
        # System message (as user message since Gemini doesn't have system role)
        system_content = f"SYSTEM INSTRUCTION:\n{system_prompt}\n\n"
        
        # Add context information
        context_parts = []
        if chat_history:
            context_parts.append(f"CONVERSATION HISTORY:\n{chat_history}\n")
        
        if documents_context:
            context_parts.append(f"RELEVANT DOCUMENTS:\n{documents_context}\n")
        
        if context_parts:
            system_content += "\n".join(context_parts) + "\n"
        
        system_content += f"CURRENT USER MESSAGE:\n{user_message}\n\nPlease provide a helpful response as an insurance assistant."
        
        contents.append(Content(
            role="user",
            parts=[Part.from_text(system_content)]
        ))
        
        return contents
    
    async def generate_response(
        self,
        user_message: str,
        system_prompt: str,
        chat_history: Optional[str] = None,
        documents_context: Optional[str] = None,
        max_retries: int = 3
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate response using Gemini model.
        
        Args:
            user_message: User's message
            system_prompt: System instruction
            chat_history: Previous conversation context
            documents_context: Relevant document information
            max_retries: Maximum retry attempts
            
        Returns:
            Tuple of (response_text, metadata)
            
        Raises:
            VertexAIGenerationError: If generation fails
        """
        if not self._initialized:
            await self.initialize()
        
        if not self.model:
            raise VertexAIError("Model not initialized")
        
        start_time = time.time()
        
        # Prepare conversation context
        contents = self._prepare_conversation_context(
            system_prompt=system_prompt,
            chat_history=chat_history,
            documents_context=documents_context,
            user_message=user_message
        )
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Generating response (attempt {attempt + 1}/{max_retries})")
                
                # Generate response
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.model.generate_content(contents)
                )
                
                if not response or not response.text:
                    raise VertexAIGenerationError("Empty response from model")
                
                # Calculate processing time
                processing_time = time.time() - start_time
                
                # Extract metadata
                metadata = {
                    "processing_time": processing_time,
                    "attempt": attempt + 1,
                    "model": self.model_name,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Add usage statistics if available
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    metadata.update({
                        "prompt_tokens": response.usage_metadata.prompt_token_count,
                        "completion_tokens": response.usage_metadata.candidates_token_count,
                        "total_tokens": response.usage_metadata.total_token_count
                    })
                
                logger.info(f"Response generated successfully in {processing_time:.2f}s")
                return response.text.strip(), metadata
                
            except Exception as e:
                logger.warning(f"Generation attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise VertexAIGenerationError(f"Generation failed after {max_retries} attempts: {e}")
    
    async def generate_insurance_response(
        self,
        user_message: str,
        thread_id: str,
        chat_history: Optional[str] = None,
        relevant_documents: List[str] = None,
        sources_used: List[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate insurance-specific response with context.
        
        Args:
            user_message: User's insurance inquiry
            thread_id: Conversation thread ID
            chat_history: Previous conversation history
            relevant_documents: List of relevant document contents
            sources_used: List of source document codes
            
        Returns:
            Tuple of (response_text, metadata)
        """
        if not settings.insurance:
            raise VertexAIError("Insurance configuration not loaded")
        
        # Prepare system prompt
        system_prompt = settings.insurance.system_prompt
        
        # Add available product codes to system prompt
        if settings.insurance.product_codes:
            product_info = []
            for category, codes in settings.insurance.product_codes.items():
                for code_type, code in codes.items():
                    product_info.append(f"- {code}: {category} {code_type}")
            
            system_prompt += f"\n\nAvailable Product Codes:\n" + "\n".join(product_info)
        
        # Prepare documents context
        documents_context = None
        if relevant_documents:
            doc_parts = []
            for i, doc_content in enumerate(relevant_documents):
                source = sources_used[i] if sources_used and i < len(sources_used) else f"Document {i+1}"
                doc_parts.append(f"[{source}]\n{doc_content}\n")
            
            documents_context = "\n".join(doc_parts)
        
        # Generate response
        response_text, metadata = await self.generate_response(
            user_message=user_message,
            system_prompt=system_prompt,
            chat_history=chat_history,
            documents_context=documents_context
        )
        
        # Add insurance-specific metadata
        metadata.update({
            "thread_id": thread_id,
            "sources_used": sources_used or [],
            "documents_provided": len(relevant_documents) if relevant_documents else 0
        })
        
        return response_text, metadata
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Vertex AI connection.
        
        Returns:
            Dictionary with health status information
        """
        health_info = {
            "initialized": self._initialized,
            "project_id": self.project_id,
            "location": self.location,
            "model_name": self.model_name,
            "credentials_configured": bool(settings.vertex_ai.credentials_path)
        }
        
        if self._initialized:
            try:
                # Test a simple generation
                test_contents = [Content(
                    role="user",
                    parts=[Part.from_text("Say 'Health check successful'")]
                )]
                
                start_time = time.time()
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.model.generate_content(test_contents)
                )
                
                health_info.update({
                    "test_generation": True,
                    "test_response_time": time.time() - start_time,
                    "test_response": response.text[:50] if response.text else None
                })
                
            except Exception as e:
                health_info.update({
                    "test_generation": False,
                    "test_error": str(e)
                })
        
        return health_info
    
    def is_ready(self) -> bool:
        """Check if client is ready for use"""
        return self._initialized and self.model is not None