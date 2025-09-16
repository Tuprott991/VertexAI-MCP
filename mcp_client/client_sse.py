#!/usr/bin/env python

#!/usr/bin/env python

"""
client_sse.py

Main entry point for the Insurance MCP Client.
This is the refactored modular version using Vertex AI Gemini 2.0 Flash.
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add current directory to Python path for relative imports
sys.path.insert(0, str(Path(__file__).parent))

from main import main

if __name__ == "__main__":
    main()
