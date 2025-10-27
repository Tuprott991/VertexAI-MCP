#!/usr/bin/env python

"""
terminal_server_sse.py

This file implements an MCP server using the SSE (Server-Sent Events) transport protocol.
It uses the FastMCP framework to expose tools that clients can call over an SSE connection.
SSE allows real-time, one-way communication from server to client over HTTP — ideal for pushing model updates.

The server uses:
- `Starlette` for the web server
- `uvicorn` as the ASGI server
- `FastMCP` from `mcp.server.fastmcp` to define the tools
- `SseServerTransport` to handle long-lived SSE connections
"""

#   [ MCP Client / Agent in Browser ]
#                  |
#      (connects via SSE over HTTP)
#                  |
#           [ Uvicorn Server ]
#                  |
#          (ASGI Protocol Bridge)
#                  |
#           [ Starlette App ]
#                  |
#           [ FastMCP Server ]
#                  |
#     @mcp.tool() like `add_numbers`, `run_command`



import os
import subprocess  # For running shell commands
from mcp.server.fastmcp import FastMCP  # Core MCP wrapper to define tools and expose them
from mcp.server import Server  # Underlying server abstraction used by FastMCP
from mcp.server.sse import SseServerTransport  # The SSE transport layer

from starlette.applications import Starlette  # Web framework to define routes
from starlette.routing import Route, Mount  # Routing for HTTP and message endpoints
from starlette.requests import Request  # HTTP request objects
from starlette.middleware.cors import CORSMiddleware  # CORS middleware for cross-origin requests

import uvicorn  # ASGI server to run the Starlette app
import sys
import os

# Add parent directory to path for database imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_list_of_documents, get_document_by_code, get_recent_chat_history, format_chat_history, get_customer


# --------------------------------------------------------------------------------------
# STEP 1: Initialize FastMCP instance — this acts as your "tool server"
# --------------------------------------------------------------------------------------
mcp = FastMCP("terminal")  # Name of the server for identification purposes

# Default directory where shell commands will run (used in run_command tool)
DEFAULT_WORKSPACE = os.path.expanduser("~/mcp/workspace")

# Create the workspace directory if it doesn't exist
try:
    os.makedirs(DEFAULT_WORKSPACE, exist_ok=True)
except Exception:
    # If we can't create the workspace directory, use current working directory
    DEFAULT_WORKSPACE = os.getcwd()


# --------------------------------------------------------------------------------------
# TOOL 1: run_command — execute a shell command and return output
# --------------------------------------------------------------------------------------
@mcp.tool()
async def run_command(command: str) -> str:
    """
    Executes a shell command in the default workspace and returns the result.

    Args:
        command (str): A shell command like 'ls', 'pwd', etc.

    Returns:
        str: Standard output or error message from running the command.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=DEFAULT_WORKSPACE,
            capture_output=True,
            text=True
        )
        return result.stdout or result.stderr
    except Exception as e:
        return str(e)


# TOOL 2: get all list of documents name and code

@mcp.tool()
async def list_documents() -> str:
    """
    Get list of all insurance documents with their codes and names.
    
    This tool retrieves all available insurance product documents from the database.
    Each document has a unique code that can be used with get_document_content tool.
    
    Returns:
        str: JSON string containing list of documents with code, name, and created_at
    """
    try:
        documents = await get_list_of_documents()
        return str(documents)
    except Exception as e:
        return f"Error retrieving documents: {str(e)}"


# TOOL 3: get document content by code

@mcp.tool()
async def get_document_content(code: str) -> str:
    """
    Get insurance product document content by product code.
    
    This tool retrieves the full content of a specific insurance product document
    using its unique product code. Use list_documents first to see available codes.
    
    Args:
        code (str): Insurance product code (e.g., "pru-edu-saver", "prumax")
        
    Returns:
        str: Full document content for the insurance product
    """
    try:
        document = await get_document_by_code(code)
        if document:
            return document['content']
        else:
            return f"Insurance product document with code '{code}' not found. Use list_documents to see available codes."
    except Exception as e:
        return f"Error retrieving document: {str(e)}"


# TOOL 4: get customer information by ID
@mcp.tool()
async def get_customer_info(customer_id: int) -> str:
    """
    Retrieve customer information by customer ID.
    
    This tool fetches customer details such as name, email,     and persona
    from the database using the provided customer ID.
    
    Args:
        customer_id (int): The unique ID of the customer.

    Returns:
        str: JSON string containing customer information (name, email, persona)
    """
    try:
        customer = await get_customer(customer_id)
        if customer:
            return str(customer)
        else:
            return f"Customer with ID '{customer_id}' not found."
    except Exception as e:
        return f"Error retrieving customer information: {str(e)}"
        

prudtvt_lookup_rate_table = {
                # Age: (Male rate, Female rate) - rates per 1,000 VND insurance amount
                0: (11.50, 8.33), 1: (11.64, 8.42), 2: (11.78, 8.50), 3: (11.92, 8.59),
                4: (12.07, 8.68), 5: (12.22, 8.78), 6: (12.38, 8.87), 7: (12.54, 8.97),
                8: (12.70, 9.07), 9: (12.87, 9.17), 10: (13.04, 9.27), 11: (13.22, 9.38),
                12: (13.40, 9.49), 13: (13.59, 9.60), 14: (13.78, 9.71), 15: (13.98, 9.83),
                16: (14.18, 9.95), 17: (14.39, 10.07), 18: (14.61, 10.20), 19: (14.83, 10.32),
                20: (15.06, 10.46), 21: (15.30, 10.59), 22: (15.54, 10.73), 23: (15.79, 10.87),
                24: (16.05, 11.02), 25: (16.32, 11.17), 26: (16.57, 11.29), 27: (16.82, 11.41),
                28: (17.09, 11.53), 29: (17.36, 11.66), 30: (17.64, 11.78), 31: (17.93, 11.92),
                32: (18.22, 12.05), 33: (18.53, 12.19), 34: (18.85, 12.33), 35: (19.18, 12.47),
                36: (19.81, 12.80), 37: (20.47, 13.15), 38: (21.18, 13.52), 39: (21.95, 13.90),
                40: (22.77, 14.32), 41: (23.65, 14.75), 42: (24.61, 15.22), 43: (25.64, 15.71),
                44: (26.77, 16.24), 45: (28.00, 16.80), 46: (28.77, 17.23), 47: (29.59, 17.88),
                48: (30.45, 19.14), 49: (31.36, 20.45), 50: (32.60, 21.84), 51: (35.59, 23.30),
                52: (38.85, 24.87), 53: (42.43, 26.57), 54: (46.35, 28.44), 55: (50.64, 30.52),
                56: (55.34, 32.84), 57: (60.50, 35.44), 58: (66.14, 38.35), 59: (72.33, 41.60),
                60: (79.11, 45.23), 61: (86.57, 49.30), 62: (88.61, 51.81), 63: (90.93, 54.55),
                64: (93.61, 57.53), 65: (96.69, 60.80), 66: (100.28, 64.44), 67: (104.45, 68.53),
                68: (109.15, 73.11), 69: (114.49, 78.29), 70: (120.59, 84.16)
            }

prumax_lookup_rate_table = {
                # Age: (Male rate, Female rate) - rates per 1,000 VND insurance amount
                0: (16.26, 11.11), 1: (16.31, 11.14), 2: (16.36, 11.16), 3: (16.41, 11.19),
                4: (16.46, 11.21), 5: (16.51, 11.23), 6: (16.61, 11.29), 7: (16.71, 11.34),
                8: (16.81, 11.39), 9: (16.91, 11.44), 10: (17.02, 11.50), 11: (17.12, 11.55),
                12: (17.23, 11.61), 13: (17.34, 11.66), 14: (17.45, 11.72), 15: (17.56, 11.77),
                16: (17.61, 11.81), 17: (17.65, 11.85), 18: (17.70, 11.89), 19: (17.75, 11.93),
                20: (17.80, 11.97), 21: (17.85, 12.01), 22: (17.90, 12.06), 23: (17.95, 12.10),
                24: (18.00, 12.14), 25: (18.05, 12.18), 26: (18.12, 12.22), 27: (18.19, 12.25),
                28: (18.27, 12.29), 29: (18.34, 12.32), 30: (18.41, 12.36), 31: (18.49, 12.39),
                32: (18.56, 12.43), 33: (18.64, 12.47), 34: (18.72, 12.50), 35: (18.79, 12.54),
                36: (19.43, 12.94), 37: (20.10, 13.37), 38: (20.83, 13.83), 39: (21.61, 14.32),
                40: (22.45, 14.85), 41: (23.36, 15.42), 42: (24.34, 16.04), 43: (25.41, 16.70),
                44: (26.58, 17.42), 45: (27.86, 18.21), 46: (28.80, 18.84), 47: (29.79, 19.51),
                48: (30.86, 20.23), 49: (32.01, 21.01), 50: (33.25, 21.85), 51: (34.59, 22.76),
                52: (36.04, 23.75), 53: (37.62, 24.83), 54: (39.34, 26.01), 55: (41.22, 27.31),
                56: (42.66, 28.34), 57: (44.19, 29.45), 58: (45.84, 30.65), 59: (47.62, 31.95),
                60: (49.54, 33.36), 61: (51.62, 34.91), 62: (53.89, 36.61), 63: (56.36, 38.48),
                64: (59.08, 40.55), 65: (62.06, 42.86), 66: (65.74, 45.94), 67: (69.89, 49.50),
                68: (74.59, 53.66), 69: (79.97, 58.59), 70: (86.19, 64.50)
            }

@mcp.tool()
async def calculate_premium(sum_insured: int, age: int, gender: str, product_code: str) -> str:
    """
    Calculate insurance premium based on customer age, gender, and product code.

    This tool provides a basic premium calculation based on predefined rules.
    Args:
        age (int): Age of the customer
        gender (str): Gender of the customer, gender must be like this: male, nam, m, female, nữ, nu, f
        product_code (str): Insurance product code for example: prumax, pru-edu-saver, prudtvt
    Returns:
        str: Calculated premium amount or error message
    """

    if product_code not in ["prumax", "pru-edu-saver", "prudtvt"]:
        return f"Unsupported product code '{product_code}'. Supported codes are: prumax, pru-edu-saver, prudtvt."
    try:
        lookup_rate_table = {}
        if product_code == "prudtvt":
            lookup_rate_table = prudtvt_lookup_rate_table
        elif product_code == "prumax":
            lookup_rate_table = prumax_lookup_rate_table
        elif product_code == "pru-edu-saver":
            return "Premium calculation for Pru-Edu-Saver is available at the current time."
        # Calculate premium based on rate and sum insured
        if age not in lookup_rate_table:
            return f"Age {age} is not in the valid range (0-70) for product '{product_code}'."
        
        gender_lower = gender.lower()
        if gender_lower in ["male", "nam", "m"]:
            rate = lookup_rate_table[age][0]
        elif gender_lower in ["female", "nữ", "nu", "f"]:
            rate = lookup_rate_table[age][1]
        else:
            return f"Invalid gender '{gender}'. Please use 'male'/'nam' or 'female'/'nữ'."
        
        # Calculate annual premium: (sum_insured / 1000) * rate
        annual_premium = (sum_insured / 1000) * rate

        return f"Annual premium is {annual_premium:,.0f} VND"

    except Exception as e:
        return f"Error calculating premium: {str(e)}"


# --------------------------------------------------------------------------------------
# STEP 2: Create the Starlette app to expose the tools via HTTP (using SSE)
# --------------------------------------------------------------------------------------
def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:

    """
    Constructs a Starlette app with SSE and message endpoints.

    Args:
        mcp_server (Server): The core MCP server instance.
        debug (bool): Enable debug mode for verbose logs.

    Returns:
        Starlette: The full Starlette app with routes.
    """
    # Create SSE transport handler to manage long-lived SSE connections  
    sse = SseServerTransport("/messages/")

    # Handle SSE connections using Route (requires returning Response)
    async def handle_sse(request):
        """
        Handle SSE client connection and link it to the MCP server.
        Must return a Response to avoid 'NoneType' object not callable error.
        """
        async with sse.connect_sse(
            request.scope, 
            request.receive, 
            request._send
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )
        # Return empty response to avoid NoneType error when client disconnects
        from starlette.responses import Response
        return Response()

    # Health check endpoint for Cloud Run
    async def health_check(request):
        from starlette.responses import JSONResponse
        return JSONResponse({"status": "healthy", "service": "mcp-sse-server"})
    
    # Create the Starlette app with configured endpoints
    app = Starlette(
        debug=debug,
        routes=[
            Route("/health", endpoint=health_check, methods=["GET"]),  # Health check for Cloud Run
            Route("/sse", endpoint=handle_sse, methods=["GET"]),  # For initiating SSE connection
            Mount("/messages/", app=sse.handle_post_message),    # For POST-based communication
        ],
    )
    
    # Add CORS middleware to allow cross-origin requests from browser clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, replace with specific frontend origins
        allow_credentials=True,
        allow_methods=["*"],  # Allow all methods (GET, POST, OPTIONS, etc.)
        allow_headers=["*"],  # Allow all headers
        expose_headers=["*"],  # Expose all headers to the client
    )
    
    return app


# --------------------------------------------------------------------------------------
# STEP 3: Start the server using Uvicorn if this file is run directly
# --------------------------------------------------------------------------------------
if __name__ == "__main__":
    # Get the underlying MCP server instance from FastMCP
    mcp_server = mcp._mcp_server  # Accessing private member (acceptable here)

    # Command-line arguments for host/port control
    import argparse

    parser = argparse.ArgumentParser(description='Run MCP SSE-based server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8081, help='Port to listen on')
    args = parser.parse_args()

    # Build the Starlette app with debug mode enabled
    starlette_app = create_starlette_app(mcp_server, debug=True)

    # Launch the server using Uvicorn
    uvicorn.run(starlette_app, host=args.host, port=args.port)