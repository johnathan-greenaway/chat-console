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
    parser.add_argument("--ollama-host", choices=["wsl", "windows", "auto"], 
                       help="Ollama server to use: wsl (localhost), windows (Windows host), auto (detect)")
    
    args = parser.parse_args()
    
    # Set Ollama URL based on argument
    if args.ollama_host:
        if args.ollama_host == "wsl":
            os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
        elif args.ollama_host == "windows":
            # Get Windows host IP dynamically
            try:
                import subprocess
                result = subprocess.run(["ip", "route", "show", "default"], 
                                      capture_output=True, text=True)
                windows_ip = result.stdout.split()[2] if result.returncode == 0 else "172.20.144.1"
                os.environ["OLLAMA_BASE_URL"] = f"http://{windows_ip}:11434"
            except:
                os.environ["OLLAMA_BASE_URL"] = "http://172.20.144.1:11434"
        elif args.ollama_host == "auto":
            # Try Windows first, fallback to WSL
            try:
                import subprocess
                result = subprocess.run(["ip", "route", "show", "default"], 
                                      capture_output=True, text=True)
                windows_ip = result.stdout.split()[2] if result.returncode == 0 else "172.20.144.1"
                
                import requests
                # Test Windows Ollama
                try:
                    requests.get(f"http://{windows_ip}:11434/api/tags", timeout=2)
                    os.environ["OLLAMA_BASE_URL"] = f"http://{windows_ip}:11434"
                    print(f"Using Windows Ollama at {windows_ip}:11434")
                except:
                    # Fallback to WSL
                    os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
                    print("Using WSL Ollama at localhost:11434")
            except:
                os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
    
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