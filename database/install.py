"""
Installation and upgrade script for the new async database module.

Run this script to:
1. Install required dependencies
2. Initialize database tables
3. Run tests to verify everything works

Usage:
    python database/install.py
"""

import asyncio
import subprocess
import sys
import os
from pathlib import Path


def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "="*70)
    print(f" {text}")
    print("="*70 + "\n")


def install_dependencies():
    """Install required Python packages"""
    print_header("Step 1: Installing Dependencies")
    
    requirements = [
        "asyncpg==0.29.0",
        "aiofiles==23.2.1",
        "python-dotenv",
        "pytest==7.4.3",
        "pytest-asyncio==0.21.1"
    ]
    
    print("Installing packages:")
    for req in requirements:
        print(f"  - {req}")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--upgrade"
        ] + requirements)
        print("\n✓ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Failed to install dependencies: {e}")
        return False


def check_environment():
    """Check if required environment variables are set"""
    print_header("Step 2: Checking Environment Variables")
    
    required_vars = [
        "POSTGRES_DATABASE",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT"
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask password
            display_value = "***" if "PASSWORD" in var else value
            print(f"✓ {var}={display_value}")
        else:
            print(f"✗ {var} is not set")
            missing.append(var)
    
    if missing:
        print(f"\n⚠ Warning: {len(missing)} environment variable(s) missing")
        print("Please set them in your .env file or environment")
        return False
    
    print("\n✓ All environment variables are set")
    return True


async def initialize_database():
    """Initialize database tables"""
    print_header("Step 3: Initializing Database Tables")
    
    try:
        # Import after installation
        from database import (
            get_connection_pool,
            close_connection_pool,
            init_chat_history_table,
            init_document_table,
            health_check
        )
        
        # Create connection pool
        print("Creating connection pool...")
        await get_connection_pool()
        print("✓ Connection pool created")
        
        # Health check
        print("\nRunning health check...")
        is_healthy = await health_check()
        if not is_healthy:
            print("✗ Database health check failed")
            return False
        print("✓ Database is healthy")
        
        # Initialize tables
        print("\nInitializing tables...")
        await init_chat_history_table()
        print("✓ Chat history table initialized")
        
        await init_document_table()
        print("✓ Document table initialized")
        
        # Cleanup
        await close_connection_pool()
        print("\n✓ Database initialized successfully")
        return True
        
    except Exception as e:
        print(f"\n✗ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_tests():
    """Run the test suite"""
    print_header("Step 4: Running Tests")
    
    test_file = Path(__file__).parent / "test_async_db.py"
    
    if not test_file.exists():
        print("⚠ Test file not found, skipping tests")
        return True
    
    print("Running test suite...")
    print("(This may take a minute...)\n")
    
    try:
        # Import and run tests
        from database import close_connection_pool
        
        # Import test module
        sys.path.insert(0, str(test_file.parent))
        from test_async_db import run_all_tests
        
        success = await run_all_tests()
        
        if success:
            print("\n✓ All tests passed")
        else:
            print("\n✗ Some tests failed")
        
        return success
        
    except Exception as e:
        print(f"\n⚠ Could not run tests: {e}")
        print("You can run tests manually with: python database/test_async_db.py")
        return True  # Don't fail installation if tests can't run


def print_next_steps():
    """Print next steps for the user"""
    print_header("Installation Complete!")
    
    print("Next steps:")
    print()
    print("1. Review the documentation:")
    print("   - database/README.md - API reference")
    print("   - database/MIGRATION_GUIDE.md - Migration guide")
    print("   - database/example_usage.py - Usage examples")
    print()
    print("2. Migrate your code:")
    print("   - Convert functions to async")
    print("   - Update import statements")
    print("   - Use 'await' for database calls")
    print()
    print("3. Test your application:")
    print("   - Run: python database/example_usage.py")
    print("   - Run: python database/test_async_db.py")
    print()
    print("4. Update your application startup:")
    print("   ```python")
    print("   from database import get_connection_pool, close_connection_pool")
    print("   ")
    print("   async def startup():")
    print("       await get_connection_pool()")
    print("   ")
    print("   async def shutdown():")
    print("       await close_connection_pool()")
    print("   ```")
    print()
    print("Need help? Check database/MIGRATION_GUIDE.md")
    print()


async def main():
    """Main installation process"""
    print_header("Async Database Module Installation")
    
    print("This script will:")
    print("  1. Install required dependencies")
    print("  2. Check environment variables")
    print("  3. Initialize database tables")
    print("  4. Run tests to verify installation")
    print()
    input("Press Enter to continue or Ctrl+C to cancel...")
    
    # Step 1: Install dependencies
    if not install_dependencies():
        print("\n✗ Installation failed at dependency installation")
        return False
    
    # Step 2: Check environment
    env_ok = check_environment()
    if not env_ok:
        print("\n⚠ Continuing with missing environment variables...")
        print("Database initialization will fail without proper configuration")
        response = input("\nContinue anyway? (y/N): ")
        if response.lower() != 'y':
            print("\nInstallation cancelled")
            return False
    
    # Step 3: Initialize database
    if env_ok:
        if not await initialize_database():
            print("\n✗ Installation failed at database initialization")
            return False
    else:
        print("\n⚠ Skipping database initialization (environment not configured)")
    
    # Step 4: Run tests
    if env_ok:
        await run_tests()
    else:
        print("\n⚠ Skipping tests (environment not configured)")
    
    # Print next steps
    print_next_steps()
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Installation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
