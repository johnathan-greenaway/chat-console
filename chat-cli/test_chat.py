#!/usr/bin/env python3
"""
Test script for chat-cli to verify auto-titling and streaming response features.
"""
import os
import sys
import asyncio
from app.main import SimpleChatApp

def main():
    """Run the chat application with test message."""
    print("Starting chat-cli test...")
    
    # Set up test message
    test_message = "Who is Darren Sharper?"
    
    # Run the app with the test message
    app = SimpleChatApp(initial_text=test_message)
    app.run()

if __name__ == "__main__":
    main()
