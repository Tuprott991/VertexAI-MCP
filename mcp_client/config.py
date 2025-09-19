"""
config.py

Configuration management using Pydantic for the Insurance MCP Client.
Handles environment variables, Vertex AI authentication, and application settings.
"""

import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class VertexAIConfig(BaseModel):
    """Vertex AI configuration model"""
    project_id: str = Field(..., description="Google Cloud Project ID")
    location: str = Field(default="us-central1", description="Vertex AI location")
    model_name: str = Field(default="gemini-2.5-flash", description="Gemini model name")
    credentials_path: Optional[str] = Field(None, description="Path to service account JSON")
    max_tokens: int = Field(default=8192, description="Maximum tokens for response")
    temperature: float = Field(default=0.7, description="Temperature for generation")
    top_p: float = Field(default=0.8, description="Top-p for generation")
    top_k: int = Field(default=40, description="Top-k for generation")


class DatabaseConfig(BaseModel):
    host: str = Field(..., description="Database host")
    port: int = Field(5432, description="Database port")
    name: str = Field(..., description="Database name")
    user: str = Field(..., description="Database user")
    password: str = Field(..., description="Database password")
    sslmode: str = Field("prefer", description="SSL mode")
    channel_binding: str = Field("prefer", description="Channel binding")
    
    @property
    def connection_string(self) -> str:
        """Generate PostgreSQL connection string with SSL parameters"""
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
            f"?sslmode={self.sslmode}&channel_binding={self.channel_binding}"
        )

class MCPConfig(BaseModel):
    """MCP server configuration model"""
    server_url: str = Field(default="http://localhost:8081", description="MCP server URL")
    server_host: str = Field(default="localhost", description="MCP server host")
    server_port: int = Field(default=8081, description="MCP server port")
    connection_timeout: int = Field(default=30, description="Connection timeout in seconds")
    retry_attempts: int = Field(default=3, description="Number of retry attempts")

# This is expose API to Prudaily
class APIConfig(BaseModel):
    """API server configuration model"""
    host: str = Field(default="0.0.0.0", description="API host")
    port: int = Field(default=8080, description="API port")
    # Maybe this this cors use only for Prudaily frontend
    cors_origins: List[str] = Field(default=["*"], description="CORS allowed origins")
    debug: bool = Field(default=False, description="Debug mode")
    
    @field_validator('cors_origins', pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v


class InsuranceConfig(BaseModel):
    """Insurance-specific configuration"""
    system_prompt: str = Field(..., description="System prompt for insurance assistant")
    product_codes: Dict[str, Dict[str, str]] = Field(..., description="Insurance product codes")
    conversation_starters: List[str] = Field(default=[], description="Conversation starters")
    response_format: Dict[str, Any] = Field(default={}, description="Response formatting options")
    max_history_messages: int = Field(default=10, description="Maximum chat history messages")


class Settings(BaseSettings):
    """Main application settings"""
    
    # Environment
    environment: str = Field(default="development", description="Environment name")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Component configurations
    vertex_ai: VertexAIConfig = Field(default_factory=VertexAIConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    
    # Insurance configuration will be loaded from prompt.json
    insurance: Optional[InsuranceConfig] = None
    
    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        case_sensitive = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_insurance_config()
        self._load_vertex_ai_credentials()
    
    def _load_insurance_config(self):
        """Load insurance configuration from prompt.json"""
        try:
            prompt_file = Path(__file__).parent / "prompt.json"
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompt_data = json.load(f)
                    self.insurance = InsuranceConfig(**prompt_data)
        except Exception as e:
            print(f"Warning: Failed to load insurance config: {e}")
            # Set default insurance config
            self.insurance = InsuranceConfig(
                system_prompt="You are an insurance assistant.",
                product_codes={},
                conversation_starters=[],
                response_format={}
            )
    
    def _load_vertex_ai_credentials(self):
        """Set up Vertex AI credentials"""
        if self.vertex_ai.credentials_path and Path(self.vertex_ai.credentials_path).exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.vertex_ai.credentials_path


# Pydantic models for API requests/responses
class ChatMessage(BaseModel):
    """Chat message model"""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now, description="Message timestamp")
    
    @field_validator('role')
    def validate_role(cls, v):
        if v not in ['user', 'assistant', 'system']:
            raise ValueError('Role must be user, assistant, or system')
        return v


class ChatRequest(BaseModel):
    """Chat request model"""
    thread_id: str = Field(..., description="Unique thread identifier")
    user_id: int = Field(..., description="User identifier")
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    include_history: bool = Field(default=True, description="Include chat history in context")
    max_history: int = Field(default=10, description="Maximum history messages to include")
    
    @field_validator('message')
    def validate_message(cls, v):
        if not v.strip():
            raise ValueError('Message cannot be empty')
        return v.strip()


class ChatResponse(BaseModel):
    """Chat response model"""
    thread_id: str = Field(..., description="Thread identifier")
    response: str = Field(..., description="Assistant response")
    sources: List[str] = Field(default=[], description="Information sources used")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    tokens_used: Optional[int] = Field(None, description="Tokens used in generation")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")


class DocumentInfo(BaseModel):
    """Document information model"""
    code: str = Field(..., description="Document code")
    name: str = Field(..., description="Document name")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")


class DocumentResponse(BaseModel):
    """Document response model"""
    documents: List[DocumentInfo] = Field(..., description="List of documents")
    total: int = Field(..., description="Total number of documents")


class DocumentContentResponse(BaseModel):
    """Document content response model"""
    product_code: str = Field(..., description="Product code")
    name: Optional[str] = Field(None, description="Document name")
    content: str = Field(..., description="Document content")
    retrieved_at: datetime = Field(default_factory=datetime.now, description="Retrieval timestamp")


class ToolCallRequest(BaseModel):
    """Tool call request model"""
    tool_name: str = Field(..., description="Name of the tool to call")
    arguments: Dict[str, Any] = Field(default={}, description="Tool arguments")


class ToolCallResponse(BaseModel):
    """Tool call response model"""
    tool: str = Field(..., description="Tool name")
    result: Any = Field(..., description="Tool execution result")
    success: bool = Field(..., description="Execution success status")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_time: Optional[float] = Field(None, description="Execution time in seconds")


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(default_factory=datetime.now, description="Check timestamp")
    mcp_connected: bool = Field(..., description="MCP server connection status")
    vertex_ai_configured: bool = Field(..., description="Vertex AI configuration status")
    database_connected: bool = Field(..., description="Database connection status")
    available_tools: List[str] = Field(default=[], description="Available MCP tools")
    version: str = Field(default="1.0.0", description="Application version")


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request identifier")


# Global settings instance
settings = Settings()