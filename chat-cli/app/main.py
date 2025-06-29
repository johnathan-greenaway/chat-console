#!/usr/bin/env python3
"""
Main entry point for Pure Console Chat CLI
No Textual dependencies - pure terminal interface
"""

import sys
import os
import asyncio
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Pure Console Chat CLI")
    parser.add_argument("initial_message", nargs="?", help="Initial message to send")
    parser.add_argument("--console", action="store_true", help="Force console mode (default)")
    
    args = parser.parse_args()
    
    # Run the console interface directly
    try:
        from .console_interface import main as console_main
        console_main()
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()