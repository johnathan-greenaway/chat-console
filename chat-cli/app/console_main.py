#!/usr/bin/env python3
"""
Entry point for the pure console version of Chat CLI
"""

import os
import sys
import asyncio
import argparse

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