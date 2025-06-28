#!/usr/bin/env python3
"""
Pure Console Chat CLI - No Textual Dependencies
A true terminal interface following Dieter Rams principles
"""

import os
import sys
import asyncio
import argparse
import signal
import threading
import time
from datetime import datetime
from typing import List, Optional, Dict, Any
import shutil

# Add app to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from app.models import Message, Conversation
from app.database import ChatDatabase
from app.config import CONFIG, save_config
from app.utils import resolve_model_id, generate_conversation_title
from app.console_utils import console_streaming_response, apply_style_prefix
from app.api.base import BaseModelClient

class ConsoleUI:
    """Pure console UI following Rams design principles"""
    
    def __init__(self):
        self.width = min(shutil.get_terminal_size().columns, 120)
        self.height = shutil.get_terminal_size().lines
        self.db = ChatDatabase()
        self.current_conversation: Optional[Conversation] = None
        self.messages: List[Message] = []
        self.selected_model = resolve_model_id(CONFIG["default_model"])
        self.selected_style = CONFIG["default_style"]
        self.running = True
        self.generating = False
        
    def clear_screen(self):
        """Clear the terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def get_border_chars(self):
        """Get clean ASCII border characters"""
        return {
            'horizontal': '─',
            'vertical': '│',
            'top_left': '┌',
            'top_right': '┐',
            'bottom_left': '└',
            'bottom_right': '┘',
            'tee_down': '┬',
            'tee_up': '┴',
            'tee_right': '├',
            'tee_left': '┤'
        }
    
    def draw_border_line(self, width: int, position: str = 'top') -> str:
        """Draw a clean border line"""
        chars = self.get_border_chars()
        
        if position == 'top':
            return chars['top_left'] + chars['horizontal'] * (width - 2) + chars['top_right']
        elif position == 'bottom':
            return chars['bottom_left'] + chars['horizontal'] * (width - 2) + chars['bottom_right']
        elif position == 'middle':
            return chars['tee_right'] + chars['horizontal'] * (width - 2) + chars['tee_left']
        else:
            return chars['horizontal'] * width
    
    def draw_header(self) -> List[str]:
        """Draw the application header"""
        from app import __version__
        chars = self.get_border_chars()
        
        lines = []
        
        # Top border with title and model info
        title = f" Chat Console v{__version__} "
        model_info = f" Model: {self.selected_model} "
        
        # Calculate spacing
        used_space = len(title) + len(model_info)
        remaining = self.width - used_space - 2
        spacing = chars['horizontal'] * max(0, remaining)
        
        header_line = chars['top_left'] + title + spacing + model_info + chars['top_right']
        lines.append(header_line)
        
        # Conversation title
        conv_title = self.current_conversation.title if self.current_conversation else "New Conversation"
        title_line = chars['vertical'] + f" {conv_title} ".ljust(self.width - 2) + chars['vertical']
        lines.append(title_line)
        
        # Separator
        lines.append(self.draw_border_line(self.width, 'middle'))
        
        return lines
    
    def draw_footer(self) -> List[str]:
        """Draw the footer with controls"""
        chars = self.get_border_chars()
        
        controls = "[q] Quit  [n] New  [h] History  [s] Settings  [ctrl+c] Cancel"
        footer_line = chars['vertical'] + f" {controls} ".ljust(self.width - 2) + chars['vertical']
        
        return [
            self.draw_border_line(self.width, 'middle'),
            footer_line,
            self.draw_border_line(self.width, 'bottom')
        ]
    
    def _detect_and_highlight_code(self, content: str) -> str:
        """Detect and highlight code blocks in content"""
        if not CONFIG.get("highlight_code", True):
            return content
            
        try:
            # Try to import colorama for terminal colors
            from colorama import Fore, Style, init
            init()  # Initialize colorama
            
            lines = content.split('\n')
            result_lines = []
            in_code_block = False
            
            for line in lines:
                # Detect code block markers
                if line.strip().startswith('```'):
                    in_code_block = not in_code_block
                    if in_code_block:
                        result_lines.append(f"{Fore.CYAN}{line}{Style.RESET_ALL}")
                    else:
                        result_lines.append(f"{Fore.CYAN}{line}{Style.RESET_ALL}")
                elif in_code_block:
                    # Highlight code content
                    result_lines.append(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
                elif '`' in line and line.count('`') >= 2:
                    # Inline code highlighting
                    import re
                    highlighted = re.sub(
                        r'`([^`]+)`', 
                        f'{Fore.GREEN}`\\1`{Style.RESET_ALL}', 
                        line
                    )
                    result_lines.append(highlighted)
                else:
                    result_lines.append(line)
            
            return '\n'.join(result_lines)
            
        except ImportError:
            # Colorama not available, return content as-is
            return content
        except Exception:
            # Any other error, return content as-is
            return content
    
    def _improved_word_wrap(self, text: str, width: int) -> List[str]:
        """Improved word wrapping that preserves code blocks and handles long lines"""
        lines = text.split('\n')
        wrapped_lines = []
        
        for line in lines:
            # Handle very long lines (like URLs or code)
            if len(line) > width:
                # If it looks like code or a URL, don't break it aggressively
                if (line.strip().startswith(('http', 'https', 'www', '  ', '\t')) or 
                    '```' in line or line.count('`') >= 2):
                    # Add as-is but truncate if necessary
                    if len(line) > width:
                        wrapped_lines.append(line[:width-3] + "...")
                    else:
                        wrapped_lines.append(line)
                else:
                    # Normal word wrapping
                    words = line.split()
                    current_line = ""
                    
                    for word in words:
                        if len(current_line) + len(word) + 1 <= width:
                            if current_line:
                                current_line += " "
                            current_line += word
                        else:
                            if current_line:
                                wrapped_lines.append(current_line)
                            current_line = word
                    
                    if current_line:
                        wrapped_lines.append(current_line)
            else:
                # Line fits, add as-is
                wrapped_lines.append(line)
        
        return wrapped_lines or [""]
    
    def format_message(self, message: Message) -> List[str]:
        """Enhanced message formatting with code highlighting and better wrapping"""
        timestamp = datetime.now().strftime("%H:%M")
        chars = self.get_border_chars()
        
        # Calculate available width for content
        content_width = self.width - 10  # Account for borders and timestamp
        
        # Apply code highlighting if enabled
        highlighted_content = self._detect_and_highlight_code(message.content)
        
        # Use improved word wrapping
        lines = self._improved_word_wrap(highlighted_content, content_width)
        
        # Format lines with proper spacing
        formatted_lines = []
        for i, line in enumerate(lines):
            if i == 0:
                # First line with timestamp and role indicator
                role_indicator = "👤" if message.role == "user" else "🤖"
                prefix = f" {role_indicator} {timestamp} "
                formatted_line = chars['vertical'] + prefix + line.ljust(content_width - len(role_indicator)) + chars['vertical']
            else:
                # Continuation lines with proper indentation
                prefix = "        "  # Align with content
                formatted_line = chars['vertical'] + prefix + line.ljust(content_width) + chars['vertical']
            formatted_lines.append(formatted_line)
        
        # Add empty line for spacing
        empty_line = chars['vertical'] + " " * (self.width - 2) + chars['vertical']
        formatted_lines.append(empty_line)
        
        return formatted_lines
    
    def draw_messages(self) -> List[str]:
        """Draw all messages in the conversation"""
        lines = []
        chars = self.get_border_chars()
        
        if not self.messages:
            # Empty state
            empty_line = chars['vertical'] + " " * (self.width - 2) + chars['vertical']
            lines.extend([empty_line] * 3)
            center_text = "Start a conversation by typing a message below"
            centered_line = chars['vertical'] + center_text.center(self.width - 2) + chars['vertical']
            lines.append(centered_line)
            lines.extend([empty_line] * 3)
        else:
            # Display messages
            for message in self.messages[-10:]:  # Show last 10 messages
                lines.extend(self.format_message(message))
        
        return lines
    
    def draw_input_area(self, current_input: str = "", prompt: str = "Type your message") -> List[str]:
        """Draw the input area"""
        chars = self.get_border_chars()
        lines = []
        
        # Input prompt
        prompt_line = chars['vertical'] + f" {prompt}: ".ljust(self.width - 2) + chars['vertical']
        lines.append(prompt_line)
        
        # Input field
        input_content = current_input
        if len(input_content) > self.width - 6:
            input_content = input_content[-(self.width - 9):] + "..."
        
        input_line = chars['vertical'] + f" > {input_content}".ljust(self.width - 2) + chars['vertical']
        lines.append(input_line)
        
        # Show generating indicator if needed
        if self.generating:
            status_line = chars['vertical'] + " ● Generating response...".ljust(self.width - 2) + chars['vertical']
            lines.append(status_line)
        
        return lines
    
    def draw_screen(self, current_input: str = "", input_prompt: str = "Type your message"):
        """Draw the complete screen"""
        self.clear_screen()
        
        # Calculate layout
        header_lines = self.draw_header()
        footer_lines = self.draw_footer()
        input_lines = self.draw_input_area(current_input, input_prompt)
        
        # Calculate available space for messages
        used_lines = len(header_lines) + len(footer_lines) + len(input_lines)
        available_lines = self.height - used_lines - 2
        
        # Draw header
        for line in header_lines:
            print(line)
        
        # Draw messages
        message_lines = self.draw_messages()
        chars = self.get_border_chars()
        
        # Pad or truncate message area
        if len(message_lines) < available_lines:
            # Pad with empty lines
            empty_line = chars['vertical'] + " " * (self.width - 2) + chars['vertical']
            message_lines.extend([empty_line] * (available_lines - len(message_lines)))
        else:
            # Truncate to fit
            message_lines = message_lines[-available_lines:]
        
        for line in message_lines:
            print(line)
        
        # Draw input area
        for line in input_lines:
            print(line)
        
        # Draw footer
        for line in footer_lines:
            print(line)
        
        # Position cursor
        print("\033[A" * (len(footer_lines) + len(input_lines) - 1), end="")
        print(f"\033[{len(current_input) + 4}C", end="")
        sys.stdout.flush()
    
    def get_input(self, prompt: str = "Type your message") -> str:
        """Get user input with real-time display updates"""
        current_input = ""
        
        while True:
            self.draw_screen(current_input, prompt)
            
            # Get single character
            if os.name == 'nt':
                import msvcrt
                char = msvcrt.getch().decode('utf-8', errors='ignore')
            else:
                import termios, tty
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(sys.stdin.fileno())
                    char = sys.stdin.read(1)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            
            # Handle special keys
            if char == '\r' or char == '\n':
                # Enter - submit input
                return current_input.strip()
            elif char == '\x03':
                # Ctrl+C
                if self.generating:
                    self.generating = False
                    return ""
                else:
                    raise KeyboardInterrupt
            elif char == '\x7f' or char == '\x08':
                # Backspace
                current_input = current_input[:-1]
            elif char == '\x1b':
                # Escape sequence - handle arrow keys, etc.
                continue
            elif ord(char) >= 32:
                # Printable character
                current_input += char
    
    async def create_new_conversation(self):
        """Create a new conversation"""
        title = "New Conversation"
        conversation_id = self.db.create_conversation(title, self.selected_model, self.selected_style)
        conversation_data = self.db.get_conversation(conversation_id)
        self.current_conversation = Conversation.from_dict(conversation_data)
        self.messages = []
        
    async def add_message(self, role: str, content: str):
        """Add a message to the current conversation"""
        message = Message(role=role, content=content)
        self.messages.append(message)
        
        if self.current_conversation:
            self.db.add_message(self.current_conversation.id, role, content)
    
    async def _generate_title_background(self, first_message: str):
        """Generate conversation title in background after first user message"""
        if not CONFIG.get("generate_dynamic_titles", True):
            return
            
        try:
            # Get client for title generation
            client = await BaseModelClient.get_client_for_model(self.selected_model)
            
            # Generate title
            new_title = await generate_conversation_title(first_message, self.selected_model, client)
            
            # Update conversation title in database and UI
            if self.current_conversation and new_title and new_title != "New Conversation":
                self.db.update_conversation_title(self.current_conversation.id, new_title)
                self.current_conversation.title = new_title
                
        except Exception as e:
            # Silently fail - title generation is not critical
            pass
    
    async def generate_response(self, user_message: str):
        """Generate AI response with improved cancellation handling"""
        self.generating = True
        assistant_message = None
        
        try:
            # Add user message
            await self.add_message("user", user_message)
            
            # Generate title for first user message if this is a new conversation
            if (self.current_conversation and 
                self.current_conversation.title == "New Conversation" and 
                len([msg for msg in self.messages if msg.role == "user"]) == 1):
                # Generate title in background (non-blocking)
                asyncio.create_task(self._generate_title_background(user_message))
            
            # Prepare messages for API
            api_messages = []
            for msg in self.messages:
                api_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # Get client
            client = await BaseModelClient.get_client_for_model(self.selected_model)
            
            # Add assistant message
            assistant_message = Message(role="assistant", content="")
            self.messages.append(assistant_message)
            
            # Stream response
            full_response = ""
            cancelled = False
            
            def update_callback(content: str):
                nonlocal full_response
                if not self.generating:
                    return
                full_response = content
                assistant_message.content = content
                # Redraw screen periodically
                self.draw_screen("", "Generating response")
            
            # Apply style to messages
            styled_messages = apply_style_prefix(api_messages, self.selected_style)
            
            # Generate streaming response with cancellation support
            try:
                async for chunk in console_streaming_response(
                    styled_messages, self.selected_model, self.selected_style, client, update_callback
                ):
                    if not self.generating:
                        cancelled = True
                        break
                    if chunk:
                        full_response += chunk
                        
            except asyncio.CancelledError:
                cancelled = True
                raise
            
            # Handle cancellation cleanup
            if cancelled or not self.generating:
                if assistant_message and assistant_message in self.messages:
                    # Remove incomplete assistant message
                    self.messages.remove(assistant_message)
                self.draw_screen("", "Generation cancelled")
                return
            
            # Update final message content
            assistant_message.content = full_response
            
            # Save final response only if complete
            if self.current_conversation and full_response and not cancelled:
                self.db.add_message(self.current_conversation.id, "assistant", full_response)
                
        except KeyboardInterrupt:
            # Handle direct keyboard interrupt
            if assistant_message and assistant_message in self.messages:
                self.messages.remove(assistant_message)
            self.draw_screen("", "Generation cancelled")
            
        except Exception as e:
            # Handle other errors
            error_msg = f"Error: {str(e)}"
            if assistant_message:
                assistant_message.content = error_msg
            else:
                await self.add_message("assistant", error_msg)
        finally:
            self.generating = False
    
    def show_history(self):
        """Show conversation history"""
        conversations = self.db.get_all_conversations(limit=20)
        if not conversations:
            input("No conversations found. Press Enter to continue...")
            return
        
        self.clear_screen()
        print("=" * self.width)
        print("CONVERSATION HISTORY".center(self.width))
        print("=" * self.width)
        
        for i, conv in enumerate(conversations):
            print(f"{i+1:2d}. {conv['title'][:60]} ({conv['model']})")
        
        print("\nEnter conversation number to load (or press Enter to cancel):")
        
        try:
            choice = input("> ").strip()
            if choice and choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(conversations):
                    # Load conversation
                    conv_data = self.db.get_conversation(conversations[idx]['id'])
                    self.current_conversation = Conversation.from_dict(conv_data)
                    self.messages = [Message(**msg) for msg in self.current_conversation.messages]
        except (ValueError, KeyboardInterrupt):
            pass
    
    def show_settings(self):
        """Show enhanced settings menu with style selection and persistence"""
        while True:
            self.clear_screen()
            print("=" * self.width)
            print("SETTINGS".center(self.width))
            print("=" * self.width)
            
            print(f"Current Model: {CONFIG['available_models'][self.selected_model]['display_name']}")
            print(f"Current Style: {CONFIG['user_styles'][self.selected_style]['name']}")
            print()
            print("What would you like to change?")
            print("1. Model")
            print("2. Response Style")
            print("3. Save Settings")
            print("0. Back to Chat")
            
            try:
                choice = input("\n> ").strip()
                
                if choice == "1":
                    # Model selection
                    self._select_model()
                elif choice == "2":
                    # Style selection
                    self._select_style()
                elif choice == "3":
                    # Save settings
                    self._save_settings()
                elif choice == "0" or choice == "":
                    break
                    
            except (ValueError, KeyboardInterrupt):
                break
    
    def _select_model(self):
        """Model selection submenu"""
        self.clear_screen()
        print("=" * self.width)
        print("MODEL SELECTION".center(self.width))
        print("=" * self.width)
        
        models = list(CONFIG["available_models"].keys())
        for i, model in enumerate(models):
            marker = "►" if model == self.selected_model else " "
            display_name = CONFIG["available_models"][model]["display_name"]
            provider = CONFIG["available_models"][model]["provider"]
            print(f"{marker} {i+1:2d}. {display_name} ({provider})")
        
        print("\nEnter model number to select (or press Enter to cancel):")
        
        try:
            choice = input("> ").strip()
            if choice and choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(models):
                    old_model = self.selected_model
                    self.selected_model = models[idx]
                    print(f"Model changed from {old_model} to {self.selected_model}")
                    input("Press Enter to continue...")
        except (ValueError, KeyboardInterrupt):
            pass
    
    def _select_style(self):
        """Style selection submenu"""
        self.clear_screen()
        print("=" * self.width)
        print("RESPONSE STYLE SELECTION".center(self.width))
        print("=" * self.width)
        
        styles = list(CONFIG["user_styles"].keys())
        for i, style in enumerate(styles):
            marker = "►" if style == self.selected_style else " "
            name = CONFIG["user_styles"][style]["name"]
            description = CONFIG["user_styles"][style]["description"]
            print(f"{marker} {i+1:2d}. {name}")
            print(f"     {description}")
            print()
        
        print("Enter style number to select (or press Enter to cancel):")
        
        try:
            choice = input("> ").strip()
            if choice and choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(styles):
                    old_style = self.selected_style
                    self.selected_style = styles[idx]
                    print(f"Style changed from {old_style} to {self.selected_style}")
                    input("Press Enter to continue...")
        except (ValueError, KeyboardInterrupt):
            pass
    
    def _save_settings(self):
        """Save current settings to config file"""
        try:
            CONFIG["default_model"] = self.selected_model
            CONFIG["default_style"] = self.selected_style
            save_config(CONFIG)
            print("Settings saved successfully!")
        except Exception as e:
            print(f"Error saving settings: {e}")
        input("Press Enter to continue...")
    
    async def run(self):
        """Main application loop"""
        # Create initial conversation
        await self.create_new_conversation()
        
        # Welcome message
        self.draw_screen("", "Type your message (or 'q' to quit)")
        
        while self.running:
            try:
                user_input = self.get_input("Type your message")
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.lower() == 'q':
                    self.running = False
                    break
                elif user_input.lower() == 'n':
                    await self.create_new_conversation()
                    continue
                elif user_input.lower() == 'h':
                    self.show_history()
                    continue
                elif user_input.lower() == 's':
                    self.show_settings()
                    continue
                
                # Generate response
                await self.generate_response(user_input)
                
            except KeyboardInterrupt:
                if self.generating:
                    self.generating = False
                    # Clean up incomplete assistant message if it exists
                    if self.messages and self.messages[-1].role == "assistant" and not self.messages[-1].content.strip():
                        self.messages.pop()
                    self.draw_screen("", "Generation cancelled - press Enter to continue")
                    input()  # Wait for user acknowledgment
                else:
                    self.running = False
                    break
            except Exception as e:
                print(f"\nError: {e}")
                input("Press Enter to continue...")

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        print("\n\nShutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """Main entry point for console version"""
    parser = argparse.ArgumentParser(description="Chat Console - Pure Terminal Version")
    parser.add_argument("--model", help="Initial model to use")
    parser.add_argument("--style", help="Response style")
    parser.add_argument("message", nargs="?", help="Initial message to send")
    
    args = parser.parse_args()
    
    # Setup signal handling
    setup_signal_handlers()
    
    # Create console UI
    console = ConsoleUI()
    
    if args.model:
        console.selected_model = resolve_model_id(args.model)
    if args.style:
        console.selected_style = args.style
    
    # Run the application
    await console.run()
    
    print("\nGoodbye!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)