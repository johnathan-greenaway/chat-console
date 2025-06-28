#!/usr/bin/env python3
"""
Entry point for the pure console version of Chat CLI
"""

import os
import sys
import asyncio
import argparse
import logging

# Setup logging suppression BEFORE any imports
def setup_console_logging():
    """Setup logging to minimize disruption to console UI - must run before imports"""
    # Set root logger to ERROR to suppress all INFO messages
    logging.getLogger().setLevel(logging.ERROR)
    
    # Completely disable all handlers to prevent any output
    logging.basicConfig(
        level=logging.CRITICAL,  # Only show CRITICAL messages
        format='',  # Empty format
        handlers=[logging.NullHandler()]  # Null handler suppresses all output
    )
    
    # Clear any existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Add only NullHandler
    logging.root.addHandler(logging.NullHandler())
    
    # Pre-emptively suppress known noisy loggers
    for logger_name in ['app', 'app.api', 'app.api.base', 'app.api.ollama', 
                        'app.utils', 'app.console_utils', 'aiohttp', 'urllib3', 
                        'httpx', 'asyncio', 'root']:
        logging.getLogger(logger_name).setLevel(logging.ERROR)
        logging.getLogger(logger_name).addHandler(logging.NullHandler())

# Apply logging suppression immediately
setup_console_logging()

async def run_console_app():
    """Run the console application"""
    from .console_chat import main as console_main
    await console_main()

def main():
    """Main entry point for console version"""
    try:
        asyncio.run(run_console_app())
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()