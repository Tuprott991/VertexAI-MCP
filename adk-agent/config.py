from dotenv import load_dotenv
import os
from dataclasses import dataclass
from google.auth import load_credentials_from_file

# Load environment variables from .env fil
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


@dataclass
class AgentConfiguration:
    """Configuration settings for the ADK Agent."""
    model: str = "gemini-2.5-flash"
    agent_name = "insurance_assistant"
    
    temperature: float = 0.2  # Lower temperature for more focused responses
    max_output_tokens: int = 1024  # Limit response length
    top_p: float = 0.95  # Nucleus sampling
    top_k: int = 40  # Top-k sampling

@dataclass
class EmbeddingConfiguration:
    """Configuration settings for embeddings."""
    model: str = ""
    dimensions: int = 768  # Embedding vector size


setup_vertex_ai_auth()
config = AgentConfiguration()