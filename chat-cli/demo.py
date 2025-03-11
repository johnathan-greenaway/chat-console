#!/usr/bin/env python3
"""
Demo script to run Chat CLI with sample data.
This creates an example conversation for demonstration purposes.
"""

import os
import sys
from datetime import datetime
import sqlite3

from app.config import DB_PATH, APP_DIR
from app.database import init_db
from app.main import main

def setup_demo():
    """Set up a demo environment with sample conversations"""
    # Create app directory if needed
    APP_DIR.mkdir(exist_ok=True)
    
    # Initialize the database
    init_db()
    
    # Connect to the database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if we already have conversations
    cursor.execute("SELECT COUNT(*) FROM conversations")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("Setting up demo conversations...")
        # Create a sample conversation
        now = datetime.now().isoformat()
        
        # Insert a conversation
        cursor.execute(
            "INSERT INTO conversations (title, model, created_at, updated_at, style) VALUES (?, ?, ?, ?, ?)",
            ("Introduction to Chat CLI", "gpt-3.5-turbo", now, now, "default")
        )
        conversation_id = cursor.lastrowid
        
        # Insert messages
        messages = [
            ("user", "Hello! Can you explain what Chat CLI is?", now),
            ("assistant", "# Welcome to Chat CLI!\n\nChat CLI is a command-line interface that allows you to interact with AI language models like GPT-3.5, GPT-4, and Claude directly from your terminal.\n\nSome key features include:\n\n- Multiple AI model support\n- Chat history and search\n- Markdown and code highlighting\n- Customizable response styles\n\nYou can use keyboard shortcuts like:\n- `n` to start a new chat\n- `s` to toggle the sidebar\n- `f` to search conversations\n\nFeel free to ask me anything else about using Chat CLI!", now)
        ]
        
        for role, content, timestamp in messages:
            cursor.execute(
                "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, timestamp)
            )
        
        # Create a second sample conversation
        cursor.execute(
            "INSERT INTO conversations (title, model, created_at, updated_at, style) VALUES (?, ?, ?, ?, ?)",
            ("Python code examples", "claude-3-sonnet", now, now, "technical")
        )
        conversation_id = cursor.lastrowid
        
        # Insert messages
        messages = [
            ("user", "Can you show me some Python code examples?", now),
            ("assistant", "# Python Code Examples\n\nHere are some useful Python code patterns:\n\n## 1. Working with files\n\n```python\n# Reading a file\nwith open('filename.txt', 'r') as file:\n    content = file.read()\n    print(content)\n\n# Writing to a file\nwith open('output.txt', 'w') as file:\n    file.write('Hello, world!')\n```\n\n## 2. List comprehensions\n\n```python\n# Create a list of squares\nsquares = [x**2 for x in range(10)]\nprint(squares)  # [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]\n\n# Filter even numbers\nevens = [x for x in range(10) if x % 2 == 0]\nprint(evens)  # [0, 2, 4, 6, 8]\n```\n\n## 3. Error handling\n\n```python\ntry:\n    result = 10 / 0\nexcept ZeroDivisionError:\n    print('Cannot divide by zero!')\nfinally:\n    print('This always executes')\n```\n\nWould you like to see examples of any specific Python functionality?", now)
        ]
        
        for role, content, timestamp in messages:
            cursor.execute(
                "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, timestamp)
            )
        
        conn.commit()
        print("Demo setup complete!")
    
    conn.close()

if __name__ == "__main__":
    # Check if running in demo mode
    setup_demo()
    
    # Run the main application
    main()
