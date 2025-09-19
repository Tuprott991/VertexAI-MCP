"""
main.py

FastAPI application for the Insurance MCP Client.
Provides REST API endpoints for insurance product inquiries with AI-powered responses.
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler

from .config import (
    settings,
    ChatRequest,
    ChatResponse,
    DocumentResponse,
    DocumentContentResponse,
    DocumentInfo,
    ToolCallRequest,
    ToolCallResponse,
    HealthResponse,
    ErrorResponse
)
from .services import InsuranceService, InsuranceServiceError

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level.upper()))
logger = logging.getLogger(__name__)

# Global service instance
insurance_service = InsuranceService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    try:
        # Startup
        logger.info("Starting Insurance MCP Client API...")
        await insurance_service.initialize()
        logger.info("Application startup completed")
        yield
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down Insurance MCP Client API...")
        await insurance_service.shutdown()
        logger.info("Application shutdown completed")


# Create FastAPI application
app = FastAPI(
    title="Insurance MCP Client API",
    description="AI-powered insurance product inquiry system using Model Context Protocol",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.api.debug else None,
    redoc_url="/redoc" if settings.api.debug else None
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not settings.api.debug:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", settings.api.host]
    )


# Exception handlers
@app.exception_handler(InsuranceServiceError)
async def insurance_service_exception_handler(request: Request, exc: InsuranceServiceError):
    """Handle insurance service errors"""
    logger.error(f"Insurance service error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Insurance service error",
            detail=str(exc),
            request_id=str(uuid.uuid4())
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            detail="An unexpected error occurred",
            request_id=str(uuid.uuid4())
        ).dict()
    )


# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    start_time = datetime.now()
    request_id = str(uuid.uuid4())
    
    # Add request ID to request state
    request.state.request_id = request_id
    
    logger.info(f"Request {request_id}: {request.method} {request.url}")
    
    response = await call_next(request)
    
    processing_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"Request {request_id} completed in {processing_time:.3f}s with status {response.status_code}")
    
    return response


# API Endpoints

@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint"""
    return {
        "message": "Insurance MCP Client API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Returns system status, connection health, and component availability.
    """
    try:
        health_info = await insurance_service.health_check()
        
        # Extract component status
        mcp_health = health_info.get("mcp_client", {})
        vertex_health = health_info.get("vertex_ai", {})
        
        return HealthResponse(
            status=health_info.get("overall_status", "unknown"),
            mcp_connected=mcp_health.get("connected", False),
            vertex_ai_configured=vertex_health.get("initialized", False),
            database_connected=True,  # Assume healthy if MCP is connected
            available_tools=mcp_health.get("available_tools", []),
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            mcp_connected=False,
            vertex_ai_configured=False,
            database_connected=False,
            available_tools=[]
        )


@app.get("/documents", response_model=DocumentResponse)
async def get_documents():
    """
    Get list of available insurance documents.
    
    Returns all insurance product documents with their codes and metadata.
    """
    try:
        documents = await insurance_service.get_documents()
        return DocumentResponse(
            documents=documents,
            total=len(documents)
        )
    except Exception as e:
        logger.error(f"Failed to get documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents"
        )


@app.get("/documents/{product_code}", response_model=DocumentContentResponse)
async def get_document_content(product_code: str):
    """
    Get specific insurance document content.
    
    Args:
        product_code: Insurance product code (e.g., 'pru-edu-saver', 'prumax')
    
    Returns:
        Document content with metadata
    """
    try:
        content = await insurance_service.get_document_content(product_code)
        
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with code '{product_code}' not found"
            )
        
        return DocumentContentResponse(
            product_code=product_code,
            content=content
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document content"
        )


@app.post("/chat", response_model=ChatResponse)
async def process_chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Process insurance inquiry with AI-powered response.
    
    This endpoint:
    1. Analyzes the user's message for insurance product mentions
    2. Retrieves relevant product documents and chat history
    3. Generates intelligent response using Vertex AI Gemini
    4. Saves the conversation to database
    
    Returns:
        AI-generated response with sources and metadata
    """
    try:
        logger.info(f"Processing chat for thread {request.thread_id}: {request.message[:100]}...")
        
        response = await insurance_service.process_inquiry(request)
        
        logger.info(f"Chat processed successfully for thread {request.thread_id}")
        return response
        
    except Exception as e:
        logger.error(f"Chat processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat message"
        )


@app.get("/chat/{thread_id}/history")
async def get_chat_history(thread_id: str, limit: int = 10):
    """
    Get chat history for a conversation thread.
    
    Args:
        thread_id: Unique conversation thread identifier
        limit: Maximum number of messages to retrieve (default: 10)
    
    Returns:
        Formatted chat history
    """
    try:
        if not insurance_service._initialized:
            await insurance_service.initialize()
        
        history = await insurance_service.mcp_client.get_chat_history(thread_id, limit)
        
        return {
            "thread_id": thread_id,
            "history": history or "No chat history found",
            "limit": limit,
            "retrieved_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get chat history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chat history"
        )


@app.post("/tools/call", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest):
    """
    Direct MCP tool calling endpoint for testing and debugging.
    
    Args:
        request: Tool name and arguments
    
    Returns:
        Tool execution result
    """
    try:
        if not insurance_service._initialized:
            await insurance_service.initialize()
        
        start_time = datetime.now()
        
        success, result, error = await insurance_service.mcp_client.call_tool_safe(
            request.tool_name,
            request.arguments
        )
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return ToolCallResponse(
            tool=request.tool_name,
            result=result,
            success=success,
            error=error,
            execution_time=execution_time
        )
        
    except Exception as e:
        logger.error(f"Tool call failed: {e}")
        return ToolCallResponse(
            tool=request.tool_name,
            result=None,
            success=False,
            error=str(e),
            execution_time=0
        )


@app.get("/tools")
async def list_tools():
    """
    Get list of available MCP tools.
    
    Returns:
        List of available tools with descriptions
    """
    try:
        if not insurance_service._initialized:
            await insurance_service.initialize()
        
        return {
            "tools": insurance_service.mcp_client.available_tools,
            "total": len(insurance_service.mcp_client.available_tools),
            "server_url": insurance_service.mcp_client.server_url
        }
        
    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tools list"
        )


@app.get("/config")
async def get_configuration():
    """
    Get current application configuration (safe subset).
    
    Returns:
        Configuration information for debugging
    """
    if not settings.api.debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Configuration endpoint only available in debug mode"
        )
    
    return {
        "environment": settings.environment,
        "api": {
            "host": settings.api.host,
            "port": settings.api.port,
            "debug": settings.api.debug
        },
        "mcp": {
            "server_url": settings.mcp.server_url,
            "connection_timeout": settings.mcp.connection_timeout
        },
        "vertex_ai": {
            "project_id": settings.vertex_ai.project_id,
            "location": settings.vertex_ai.location,
            "model_name": settings.vertex_ai.model_name,
            "credentials_configured": bool(settings.vertex_ai.credentials_path)
        },
        "insurance": {
            "max_history_messages": settings.insurance.max_history_messages if settings.insurance else None,
            "product_codes_count": len(settings.insurance.product_codes) if settings.insurance else 0
        }
    }


# Main entry point
def main():
    """Main entry point for running the application"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Insurance MCP Client API')
    parser.add_argument('--host', default=settings.api.host, help='Host to bind to')
    parser.add_argument('--port', type=int, default=settings.api.port, help='Port to listen on')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')
    args = parser.parse_args()
    
    # Update settings
    settings.api.host = args.host
    settings.api.port = args.port
    
    # Run the server
    uvicorn.run(
        "mcp_client.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload and settings.api.debug,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()