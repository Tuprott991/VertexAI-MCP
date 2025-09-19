import asyncio
import json
import os
from typing import Any

from dotenv import load_dotenv
from google.adk.agents.llm_agent import LlmAgent
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

load_dotenv()

# Set up Vertex AI authentication
def setup_vertex_ai_auth():
    """Set up Vertex AI authentication using service account JSON.

    Relies on Application Default Credentials (ADC). If a service account key
    is configured via GOOGLE_APPLICATION_CREDENTIALS, we also propagate the
    detected project ID into GOOGLE_CLOUD_PROJECT so downstream libraries that
    rely on ADC can locate the project without manual wiring.
    """
    service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not service_account_path:
        print("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
        return None, None

    print(f"Using service account from: {service_account_path}")
    credentials, project = load_credentials_from_file(service_account_path)

    # Ensure project is available to clients using ADC
    if project and not os.getenv("GOOGLE_CLOUD_PROJECT"):
        os.environ["GOOGLE_CLOUD_PROJECT"] = project
        print(f"Set GOOGLE_CLOUD_PROJECT={project}")

    # Ensure location is available for Vertex AI (required by google-genai when using Vertex backend)
    # Priority: GOOGLE_CLOUD_LOCATION | VERTEX_LOCATION | VERTEX_AI_LOCATION | default "us-central1"
    location = (
        os.getenv("GOOGLE_CLOUD_LOCATION")
        or os.getenv("VERTEX_LOCATION")
        or os.getenv("VERTEX_AI_LOCATION")
    )
    if not location:
        # Choose a widely available default for generative models
        location = "us-central1"
        print("GOOGLE_CLOUD_LOCATION not set. Defaulting to us-central1.")

    # Normalize into GOOGLE_CLOUD_LOCATION for the google-genai client
    os.environ["GOOGLE_CLOUD_LOCATION"] = location
    print(f"Using GOOGLE_CLOUD_LOCATION={location}")

    return credentials, project

def get_tools_async():
    """Gets tools from the MCP Server."""
    tools, exit_stack = MCPToolset.from_server(
        connection_params=SseConnectionParams(
            url="http://localhost:8081/sse",  # Updated to match your MCP server port
        )
    )
    print("MCP Toolset created successfully.")
    return tools, exit_stack

def create_agent():
    """Creates an ADK Agent equipped with tools from the MCP Server."""
    credentials, project = setup_vertex_ai_auth()
    if not credentials or not project:
        print("Authentication failed. Cannot create agent.")
        return None
    
    # The google.genai.types.Model pydantic schema does not accept arbitrary fields
    # like credentials/project_id. Provide only supported fields such as `name`.
    
    # Get MCP tools
    # tools, exit_stack = asyncio.run(get_tools_async())
    # print(f"Retrieved {len(tools)} tools from MCP server.")

    agent = LlmAgent(
        model="gemini-2.5-flash",
        name="insurance_assistant",
        instruction="""You are an intelligent insurance product assistant specialized in Vietnamese insurance products. 
Your role is to help customers understand insurance products, compare options, 
and provide detailed information based on official product documents.

Available Insurance Products and their codes:
- prumax: PruMax Insurance Plan
- prumax-faq: PruMax FAQ
- prumax-tnc: PruMax Terms & Conditions
- pru-edu-saver: Prudential Education Saver Plan
- pru-edu-saver-faq: Education Saver FAQ
- pru-edu-saver-tnc: Education Saver Terms & Conditions


Tools Available:
1. list_documents - Get all available insurance documents (name and code)
2. get_document_content(code) - Get specific product information using product code
   + Available codes: pru-edu-saver, pru-edu-saver-faq, pru-edu-saver-tnc, prumax, prumax-faq, prumax-tnc
3. run_command(command) - Execute system commands if needed

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
            MCPToolset(
                connection_params=SseConnectionParams(
                    url='http://localhost:8081/sse',
                    headers={'Accept': 'text/event-stream'},
                ),
                # don't want agent to do write operation
                # you can also do below
                # tool_filter=lambda tool, ctx=None: tool.name
                # not in [
                #     'write_file',
                #     'edit_file',
                #     'create_directory',
                #     'move_file',
                # ],
                tool_filter=[
                    'list_documents',
                    'get_document_content',
                    'run_command',
                ],
            )
        ],
    )
    return agent

root_agent = create_agent()