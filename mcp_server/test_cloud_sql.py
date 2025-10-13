#!/usr/bin/env python3
"""
Test script for Cloud SQL PostgreSQL connection using JSON credentials.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_cloud_sql_connection():
    """Test Cloud SQL connection with JSON credentials."""
    try:
        from cloud_sql_auth import CloudSQLAuth, get_cloud_sql_connection_string
        from mcp_server.database_old import db_pool, test_connection
        
        print("Testing Cloud SQL PostgreSQL connection with JSON credentials...")
        
        # Test 1: Check if credentials are properly configured
        print("\n1. Checking Google Cloud credentials...")
        try:
            auth = CloudSQLAuth()
            token = await auth.get_access_token()
            print(f"✓ Successfully obtained access token (length: {len(token)})")
            print(f"✓ Project ID: {auth.project_id}")
        except Exception as e:
            print(f"✗ Credential error: {e}")
            return False
        
        # Test 2: Generate connection string
        print("\n2. Generating connection string...")
        try:
            conn_string = await get_cloud_sql_connection_string()
            # Mask password in output
            safe_conn_string = conn_string.split('@')[0].split(':')[:-1]
            print(f"✓ Connection string generated: {':'.join(safe_conn_string)}:***@...")
        except Exception as e:
            print(f"✗ Connection string error: {e}")
            return False
        
        # Test 3: Test database connection
        print("\n3. Testing database connection...")
        try:
            connection_success = await test_connection()
            if connection_success:
                print("✓ Database connection successful!")
            else:
                print("✗ Database connection failed")
                return False
        except Exception as e:
            print(f"✗ Database connection error: {e}")
            return False
        
        print("\n🎉 All tests passed! Cloud SQL is properly configured.")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("Make sure you have installed the required dependencies:")
        print("pip install google-auth google-cloud-sql-connector asyncpg")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

async def main():
    """Main test function."""
    print("Cloud SQL PostgreSQL Connection Test")
    print("=" * 40)
    
    # Check environment variables
    required_vars = [
        "CLOUD_SQL_INSTANCE",
        "CLOUD_SQL_DATABASE", 
        "CLOUD_SQL_USER",
        "USE_IAM_AUTH"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"✗ Missing required environment variables: {', '.join(missing_vars)}")
        print("\nPlease set these variables in your .env file:")
        for var in missing_vars:
            print(f"  {var}=your_value")
        return
    
    # Check authentication
    auth_vars = ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CREDENTIALS_JSON"]
    if not any(os.getenv(var) for var in auth_vars):
        print("✗ Missing Google Cloud authentication.")
        print("Please set either:")
        print("  GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json")
        print("  OR")
        print("  GOOGLE_CREDENTIALS_JSON='{\"type\":\"service_account\",...}'")
        return
    
    success = await test_cloud_sql_connection()
    
    if success:
        print("\n✓ Setup is complete and working!")
    else:
        print("\n✗ Setup needs attention. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":  
    asyncio.run(main())
