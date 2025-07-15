#!/usr/bin/env python3
"""
Enhanced ASK module with screenshot and improved terminal capture support
"""

import base64
import shutil
import tempfile
from typing import Optional, List, Tuple
import subprocess
import os
import sys
from pathlib import Path


class TerminalCaptureMethod:
    """Different methods to capture terminal output"""
    
    @staticmethod
    def tmux_capture() -> Optional[str]:
        """Capture from tmux pane"""
        if os.environ.get('TMUX'):
            try:
                result = subprocess.run(['tmux', 'capture-pane', '-p'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout
            except:
                pass
        return None
    
    @staticmethod
    def screen_capture() -> Optional[str]:
        """Capture from GNU screen"""
        if os.environ.get('STY'):
            try:
                # Screen hardcopy command
                subprocess.run(['screen', '-X', 'hardcopy', '/tmp/screen_capture.txt'])
                if os.path.exists('/tmp/screen_capture.txt'):
                    with open('/tmp/screen_capture.txt', 'r') as f:
                        content = f.read()
                    os.remove('/tmp/screen_capture.txt')
                    return content
            except:
                pass
        return None
    
    @staticmethod
    def kitty_capture() -> Optional[str]:
        """Capture from kitty terminal"""
        if os.environ.get('KITTY_WINDOW_ID'):
            try:
                result = subprocess.run(['kitty', '@', 'get-text', '--ansi'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout
            except:
                pass
        return None
    
    @staticmethod
    def clipboard_capture() -> Optional[str]:
        """Try to get text from clipboard"""
        clipboard_tools = [
            ['xclip', '-selection', 'clipboard', '-o'],
            ['xsel', '--clipboard', '--output'],
            ['pbpaste'],  # macOS
            ['powershell.exe', '-command', 'Get-Clipboard']  # Windows via WSL
        ]
        
        for tool_cmd in clipboard_tools:
            if shutil.which(tool_cmd[0]):
                try:
                    result = subprocess.run(tool_cmd, capture_output=True, text=True, timeout=2)
                    if result.returncode == 0 and result.stdout.strip():
                        return result.stdout
                except:
                    continue
        return None
    
    @staticmethod
    def tty_dump() -> Optional[str]:
        """Try to dump TTY buffer (requires permissions)"""
        try:
            # This would need sudo typically
            tty = os.ttyname(sys.stdin.fileno())
            if tty.startswith('/dev/pts/'):
                # Could attempt to read from /dev/vcs* but requires root
                pass
        except:
            pass
        return None


class ScreenshotCapture:
    """Methods to capture screenshots"""
    
    @staticmethod
    def capture_screenshot() -> Optional[str]:
        """Capture a screenshot and return the file path"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        # Different screenshot tools by platform
        screenshot_commands = [
            # Linux desktop environments
            ['gnome-screenshot', '-f', temp_path],
            ['spectacle', '-b', '-n', '-o', temp_path],
            ['scrot', temp_path],
            ['import', temp_path],  # ImageMagick
            ['flameshot', 'gui', '-p', temp_path],
            
            # macOS
            ['screencapture', '-i', temp_path],
            
            # Windows via WSL
            ['powershell.exe', '-command', f'Add-Type -AssemblyName System.Drawing; '
             f'$bitmap = [System.Drawing.Bitmap]::new([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, '
             f'[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); '
             f'$graphics = [System.Drawing.Graphics]::FromImage($bitmap); '
             f'$graphics.CopyFromScreen(0, 0, 0, 0, $bitmap.Size); '
             f'$bitmap.Save("{temp_path}")']
        ]
        
        for cmd in screenshot_commands:
            if shutil.which(cmd[0]):
                try:
                    result = subprocess.run(cmd, capture_output=True, timeout=10)
                    if result.returncode == 0 and os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                        return temp_path
                except:
                    continue
        
        # Cleanup if failed
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return None
    
    @staticmethod
    def find_recent_screenshot() -> Optional[str]:
        """Look for recently created screenshots in common locations"""
        import time
        current_time = time.time()
        max_age_seconds = 60  # Screenshots created in last minute
        
        screenshot_patterns = [
            (Path.home() / 'Pictures' / 'Screenshots', 'Screenshot*.png'),
            (Path.home() / 'Desktop', 'Screenshot*.png'),
            (Path.home() / 'Desktop', 'Screen Shot*.png'),  # macOS
            (Path('/tmp'), 'screenshot*.png'),
            # WSL paths
            (Path('/mnt/c/Users') / os.environ.get('USER', '') / 'Pictures' / 'Screenshots', '*.png'),
        ]
        
        for directory, pattern in screenshot_patterns:
            if directory.exists():
                for file in directory.glob(pattern):
                    if current_time - file.stat().st_mtime < max_age_seconds:
                        return str(file)
        
        return None
    
    @staticmethod
    def encode_image_base64(image_path: str) -> str:
        """Encode image to base64 for API transmission"""
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')


class EnhancedTerminalCapture:
    """Enhanced terminal capture combining multiple methods"""
    
    @staticmethod
    def capture_all_context() -> Tuple[Optional[str], Optional[str]]:
        """
        Try all capture methods and return (text_content, image_path)
        """
        text_content = None
        image_path = None
        
        # Try text capture methods in order of preference
        capture_methods = [
            ("tmux", TerminalCaptureMethod.tmux_capture),
            ("kitty", TerminalCaptureMethod.kitty_capture),
            ("screen", TerminalCaptureMethod.screen_capture),
            ("clipboard", TerminalCaptureMethod.clipboard_capture),
        ]
        
        for name, method in capture_methods:
            result = method()
            if result:
                text_content = f"[Captured via {name}]\n{result}"
                break
        
        # Check for recent screenshots
        image_path = ScreenshotCapture.find_recent_screenshot()
        
        return text_content, image_path
    
    @staticmethod
    def interactive_capture() -> Tuple[Optional[str], Optional[str]]:
        """
        Interactive capture with user prompts
        """
        print("📸 Terminal Capture Options:")
        print("1. Auto-capture terminal text")
        print("2. Take a screenshot") 
        print("3. Use recent screenshot")
        print("4. Paste text manually")
        print("5. Skip capture")
        
        try:
            choice = input("\nSelect option (1-5): ").strip()
            
            if choice == '1':
                text, _ = EnhancedTerminalCapture.capture_all_context()
                return text, None
            elif choice == '2':
                print("📷 Taking screenshot...")
                image_path = ScreenshotCapture.capture_screenshot()
                if image_path:
                    print(f"✅ Screenshot saved: {image_path}")
                    return None, image_path
                else:
                    print("❌ Screenshot capture failed")
            elif choice == '3':
                image_path = ScreenshotCapture.find_recent_screenshot()
                if image_path:
                    print(f"✅ Found recent screenshot: {image_path}")
                    return None, image_path
                else:
                    print("❌ No recent screenshots found")
            elif choice == '4':
                print("📋 Paste your content (Ctrl+D when done):")
                text = sys.stdin.read()
                return text, None
                
        except KeyboardInterrupt:
            print("\n❌ Cancelled")
        
        return None, None


# Export the enhanced capture functionality
def get_enhanced_terminal_context():
    """Main function to get terminal context with all enhancements"""
    return EnhancedTerminalCapture.capture_all_context()


def get_screenshot():
    """Get a screenshot using available methods"""
    return ScreenshotCapture.capture_screenshot()


def encode_image(image_path):
    """Encode image for API usage"""
    return ScreenshotCapture.encode_image_base64(image_path)