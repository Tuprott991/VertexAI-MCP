"""
Cloud SQL IAM authentication utilities using JSON credentials.
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any
from google.auth import default
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import asyncpg

class CloudSQLAuth:
    """Handle Cloud SQL authentication with JSON credentials."""
    
    def __init__(self):
        self.credentials = None
        self.project_id = None
        self._initialize_credentials()
    
    def _initialize_credentials(self):
        """Initialize Google Cloud credentials from JSON file or environment."""
        # Option 1: Use service account JSON file
        json_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        json_creds_content = os.getenv("GOOGLE_CREDENTIALS_JSON")
        
        if json_creds_path and os.path.exists(json_creds_path):
            # Load from file
            self.credentials = service_account.Credentials.from_service_account_file(
                json_creds_path,
                scopes=['https://www.googleapis.com/auth/sqlservice.admin']
            )
            with open(json_creds_path, 'r') as f:
                creds_data = json.load(f)
                self.project_id = creds_data.get('project_id')
        
        elif json_creds_content:
            # Load from environment variable (JSON string)
            try:
                creds_data = json.loads(json_creds_content)
                self.credentials = service_account.Credentials.from_service_account_info(
                    creds_data,
                    scopes=['https://www.googleapis.com/auth/sqlservice.admin']
                )
                self.project_id = creds_data.get('project_id')
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in GOOGLE_CREDENTIALS_JSON: {e}")
        
        else:
            # Fallback to default credentials (e.g., when running on Google Cloud)
            self.credentials, self.project_id = default(
                scopes=['https://www.googleapis.com/auth/sqlservice.admin']
            )
        
        if not self.credentials:
            raise ValueError(
                "No Google Cloud credentials found. Please set GOOGLE_APPLICATION_CREDENTIALS "
                "or GOOGLE_CREDENTIALS_JSON environment variable."
            )

    async def get_access_token(self) -> str:
        """Get a fresh access token for Cloud SQL authentication."""
        # Refresh credentials if needed
        if not self.credentials.valid:
            self.credentials.refresh(Request())
        
        return self.credentials.token

    async def create_connection_string(
        self,
        instance_connection_name: str,
        database_name: str,
        db_user: str,
        connection_type: str = "unix"
    ) -> str:
        """
        Create connection string for Cloud SQL with IAM authentication.
        
        Args:
            instance_connection_name: Format: project:region:instance
            database_name: Name of the database
            db_user: Database user (for IAM auth, this should be the service account email without @)
            connection_type: "unix" for unix socket, "tcp" for TCP connection
        
        Returns:
            Database connection string
        """
        token = await self.get_access_token()
        
        if connection_type == "unix":
            # Unix socket connection (recommended when running on Google Cloud)
            return f"postgresql://{db_user}:{token}@/{database_name}?host=/cloudsql/{instance_connection_name}"
        elif connection_type == "tcp":
            # TCP connection (when using Cloud SQL Proxy)
            return f"postgresql://{db_user}:{token}@127.0.0.1:5432/{database_name}"
        else:
            raise ValueError("connection_type must be 'unix' or 'tcp'")

    async def create_iam_connection(
        self,
        instance_connection_name: str,
        database_name: str,
        db_user: str,
        connection_type: str = "unix"
    ) -> asyncpg.Connection:
        """
        Create a direct asyncpg connection using IAM authentication.
        
        Args:
            instance_connection_name: Format: project:region:instance
            database_name: Name of the database
            db_user: Database user (service account email without domain)
            connection_type: "unix" for unix socket, "tcp" for TCP connection
        
        Returns:
            asyncpg connection
        """
        token = await self.get_access_token()
        
        if connection_type == "unix":
            dsn = f"postgresql://{db_user}@/{database_name}?host=/cloudsql/{instance_connection_name}"
        elif connection_type == "tcp":
            dsn = f"postgresql://{db_user}@127.0.0.1:5432/{database_name}"
        else:
            raise ValueError("connection_type must be 'unix' or 'tcp'")
        
        return await asyncpg.connect(
            dsn,
            password=token,
            server_settings={
                'application_name': 'mcp-server',
                'timezone': 'UTC'
            }
        )


# Global Cloud SQL auth instance
cloud_sql_auth = CloudSQLAuth()


async def get_cloud_sql_connection_string() -> str:
    """
    Get Cloud SQL connection string using environment configuration.
    
    Required environment variables:
    - CLOUD_SQL_INSTANCE: project:region:instance
    - CLOUD_SQL_DATABASE: database name
    - CLOUD_SQL_USER: database user
    - CLOUD_SQL_CONNECTION_TYPE: "unix" or "tcp" (optional, defaults to "unix")
    
    Returns:
        Connection string for asyncpg
    """
    instance = os.getenv("CLOUD_SQL_INSTANCE")
    database = os.getenv("CLOUD_SQL_DATABASE")
    user = os.getenv("CLOUD_SQL_USER")
    connection_type = os.getenv("CLOUD_SQL_CONNECTION_TYPE", "unix")
    
    if not all([instance, database, user]):
        raise ValueError(
            "Missing required environment variables: CLOUD_SQL_INSTANCE, "
            "CLOUD_SQL_DATABASE, CLOUD_SQL_USER"
        )
    
    return await cloud_sql_auth.create_connection_string(
        instance, database, user, connection_type
    )
