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

from google.adk.sessions import InMemorySessionService, Session
from google.adk.sessions import DatabaseSessionService # Store sessions in DB
load_dotenv()

db_url = os.getenv("DATABASE_URL")
if db_url is None:
    raise ValueError("DATABASE_URL environment variable is not set.")

# session_service = DatabaseSessionService(db_url=db_url)
session_service = DatabaseSessionService(db_url=db_url)


from .config import config

def get_tools_async():
    """Gets tools from the MCP Server."""
    tools, exit_stack =  MCPToolset(
                connection_params=SseConnectionParams(
                    url='http://localhost:8081/sse',
                    headers={'Accept': 'text/event-stream'},
                ),
            )
    print("MCP Toolset created successfully.")
    return tools, exit_stack

def create_agent():
    
    # Get MCP tools
    # tools, exit_stack = asyncio.run(get_tools_async())
    # print(f"Retrieved {len(tools)} tools from MCP server.")
    agent_config = types.GenerateContentConfig(
        temperature=config.temperature,
        # max_output_tokens=config.max_output_tokens,
        top_p=config.top_p,
        top_k=config.top_k,
    )

    agent = LlmAgent(
        model=config.model,
        name=config.agent_name,
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
        generate_content_config=agent_config,
    )
    return agent

# async def run_agent(user_input: str, user_id: str = "user_1", app_name: str = "insurance_app"):
#     """Runs the agent with the given user input."""
#     print(f"[bold green]User Input:[/bold green] {user_input}")

#     # Create or retrieve session
#     session = await session_service.create_session(app_name=app_name, user_id=user_id)
#     print(f"Session ID: {session.id}")

#     # Create artifact service (optional, for storing files, images, etc.)
#     artifact_service = InMemoryArtifactService()

#     # Create the agent
#     agent = create_agent()

#     # Create the runner
#     runner = Runner(
#         agent=agent,
#         session=session,
#         session_service=session_service,
#         artifact_service=artifact_service,
#         max_iterations=3,  # Limit the number of iterations to prevent long loops
#     )

#     # Run the agent with the user input
#     response = await runner.run(user_input)

#     # Print the response
#     print(f"[bold blue]Agent Response:[/bold blue] {response}")

#     return response

root_agent = create_agent()