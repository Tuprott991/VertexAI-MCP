import asyncio
import json
import os
from typing import Any, Optional
import atexit

from dotenv import load_dotenv
from google.adk.agents.llm_agent import LlmAgent, Agent
from google.adk.artifacts.in_memory_artifact_service import (
    InMemoryArtifactService,  # Optional
)
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseConnectionParams
from google.genai import types
from google.auth import load_credentials_from_file
from rich import print

from google.adk.sessions import InMemorySessionService, Session
from google.adk.sessions import DatabaseSessionService # Store sessions in DB

from google.adk.models.lite_llm import LiteLlm
import litellm
load_dotenv()


os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", "")
MODEL_GPT_5_MINI = "openai/gpt-4o-mini"


# Use gemini-2.0-flash-exp for native Google GenAI (uses API key, no IAM permissions needed)
MODEL_GEMINI_2_5_FLASH = "gemini-2.5-flash"

mcp_server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8081/sse")

# from .config import config

# Global singleton MCP toolset to avoid reconnecting on every request
_mcp_toolset: Optional[MCPToolset] = None
_mcp_toolset_lock = asyncio.Lock()


def get_tools_async():
    """Gets tools from the MCP Server."""
    tools, exit_stack =  MCPToolset(
                connection_params=SseConnectionParams(
                    url=mcp_server_url,
                    headers={'Accept': 'text/event-stream'},
                ),
            )
    print("MCP Toolset created successfully.")
    return tools, exit_stack


def get_mcp_toolset():
    """Get or create a persistent MCP toolset (sing leton pattern).
    
    This avoids creating new SSE connections on every request,
    significantly improving performance.
    """
    global _mcp_toolset
    
    if _mcp_toolset is None:
        print("[INFO] Creating persistent MCP toolset connection...")
        _mcp_toolset = MCPToolset(
            connection_params=SseConnectionParams(
                url=mcp_server_url,
                headers={'Accept': 'text/event-stream'},
            ),
            tool_filter=[
                'list_documents',
                'get_document_content',
                'run_command',
                'get_customer_info',
                'calculate_premium',
                'web_search',
            ],
        )
        print(f"[INFO] MCP toolset created successfully. Connected to: {mcp_server_url}")
    
    return _mcp_toolset


def cleanup_mcp_connection():
    """Cleanup MCP connection on application shutdown."""
    global _mcp_toolset
    if _mcp_toolset is not None:
        print("[INFO] Cleaning up MCP toolset connection...")
        _mcp_toolset = None

# Register cleanup handler
atexit.register(cleanup_mcp_connection)

def create_agent():
    
    # Get MCP tools
    # tools, exit_stack = asyncio.run(get_tools_async())
    # print(f"Retrieved {len(tools)} tools from MCP server.")
    agent_config = types.GenerateContentConfig(
        # temperature=config.temperature,   
        # # max_output_tokens=config.max_output_tokens,     
        # top_p=config.top_p,
        # top_k=config.top_k,
    )

    agent = LlmAgent(
        # Use native model name for Google GenAI (uses GEMINI_API_KEY from .env)
        model=MODEL_GEMINI_2_5_FLASH,
        # use model = litellm(MODEL_GPT_5_MINI)  to use LiteLlm wrapper
        # use model = 

        # To use LiteLlm with Vertex AI, you would need:
        # model = LiteLlm(model="vertex_ai/gemini-2.0-flash-exp"),
        # and proper IAM permissions on your service account
        name="PruBot",
        description="An intelligent insurance product assistant specialized in Prudential Vietnam insurance products.",
        instruction="""You are an intelligent insurance product assistant specialized in Prudential Vietnam insurance products. Your name is PruBot. 
Your role is to help customers understand insurance products, compare options, 
and provide detailed information based on official product documents.
Make sure always use good words on Prudential brand and products.

Available Insurance Products and their codes:
- prumax: PruMax Insurance Plan (also known as "PRU  - BẢO VỆ TỐI ĐA")
- prumax-faq: PruMax FAQ
- prumax-tnc: PruMax Terms & Conditions
- pru-edu-saver: Prudential Education Saver Plan (also known as "PRU - TƯƠNG LAI TƯƠI SÁNG")
- pru-edu-saver-faq: Education Saver FAQ
- pru-edu-saver-tnc: Education Saver Terms & Conditions
- prudtvt: PruDtvt Insurance Plan (also known as "PRU - ĐẦU TƯ VỮNG TIẾN")
- prudtvt-faq: PruDtvt FAQ
- prudtvt-tnc: PruDtvt Terms & Conditions


Tools Available:
1. list_documents - Get all available insurance documents (name and code)
2. get_document_content(code) - Get specific product information using product code
   + Available codes: pru-edu-saver, pru-edu-saver-faq, pru-edu-saver-tnc, prumax, prumax-faq, prumax-tnc
3. run_command(command) - Execute system commands if neededx
4. get_customer_info(customer_id) - Retrieve customer information by ID
5. calculate_premium(sum_insured, age, gender, product_code) - Calculate annual premium based on sum insured, age, and gender

Guidelines:
- Use list_documents to see available products if customer asks about options
- Use get_document_content with specific product codes to provide accurate information
- Provide clear, helpful explanations in Vietnamese when appropriate
- Compare products when asked, using official document content
- Always cite which document you're referencing
- Be honest if information is not available in the documents

Your answers must be in Vietnamese.
Format: structured_with_bullet_points
""",
        tools=[
            get_mcp_toolset()  # Use persistent singleton connection
        ],
        generate_content_config=agent_config,
    )
    return agent


root_agent = create_agent()