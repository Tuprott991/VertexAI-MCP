import os
import uvicorn
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.apps.app import App

from dotenv import load_dotenv
load_dotenv()   

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

SESSION_SERVICE_URI = os.getenv("DATABASE_URL", "http://localhost:8000")

ALLOWED_ORIGINS = ["http://localhost", "http://localhost:8080", "*"]

SERVE_WEB_INTERFACE = True

app = get_fast_api_app(
    # Path to the directory containing all agent folders
    # Each subdirectory in 'agents/' represents a different agent
    # The ADK will automatically discover and load all agents from this directory
    agents_dir=os.path.join(AGENT_DIR, "agents"),
    
    # Database connection string for session persistence
    # Sessions allow maintaining conversation context across multiple requests
    session_service_uri=SESSION_SERVICE_URI,
    
    # CORS configuration to allow web browser access
    # Essential for the web interface to function properly
    allow_origins=ALLOWED_ORIGINS,
    
    # Enable/disable the web interface
    # When enabled, provides HTML pages for agent interaction
    web=SERVE_WEB_INTERFACE,

)

# root_agent = None

# app_2 = App(
#     name="pru-agent",
#     root_agent=root_agent,
#     plugins=[],
# )


if __name__ == "__main__":
    """
    Application startup configuration for both local development and Cloud Run deployment
    
    This section handles the server startup with proper configuration for different environments:
    - Local development: Uses default port 8080
    - Cloud Run: Uses the PORT environment variable provided by the platform
    
    Key configurations:
    - host="0.0.0.0": Binds to all network interfaces (required for containers)
    - port: Uses Cloud Run's PORT environment variable or defaults to 8080
    - The uvicorn server handles HTTP requests and forwards them to the FastAPI app
    """
    
    # Cloud Run provides a PORT environment variable that specifies which port to use
    # We use os.environ.get() to read this variable, with 8080 as a fallback
    # This ensures compatibility with both local development and Cloud Run deployment
    port = int(os.environ.get("PORT", 8080))
    
    # Start the uvicorn ASGI server
    # - app: The FastAPI application instance created above
    # - host="0.0.0.0": Listen on all network interfaces (required for Cloud Run)
    # - port: The port number determined above
    uvicorn.run(app, host="0.0.0.0", port=port)