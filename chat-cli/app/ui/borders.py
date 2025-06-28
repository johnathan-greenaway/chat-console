"""
ASCII Border System for Clean, Functional Design
Following Dieter Rams' principle of "Less but better"
"""

# Clean ASCII border system with different weights for hierarchy
CLEAN_BORDERS = {
    'light': {
        'top_left': '┌', 'top_right': '┐', 'bottom_left': '└', 'bottom_right': '┘',
        'horizontal': '─', 'vertical': '│', 'cross': '┼', 'tee_down': '┬',
        'tee_up': '┴', 'tee_right': '├', 'tee_left': '┤'
    },
    'heavy': {
        'top_left': '┏', 'top_right': '┓', 'bottom_left': '┗', 'bottom_right': '┛', 
        'horizontal': '━', 'vertical': '┃', 'cross': '╋', 'tee_down': '┳',
        'tee_up': '┻', 'tee_right': '┣', 'tee_left': '┫'
    },
    'double': {
        'top_left': '╔', 'top_right': '╗', 'bottom_left': '╚', 'bottom_right': '╝',
        'horizontal': '═', 'vertical': '║', 'cross': '╬', 'tee_down': '╦',
        'tee_up': '╩', 'tee_right': '╠', 'tee_left': '╣'
    }
}

def create_border_line(width: int, border_type: str = 'light', position: str = 'top') -> str:
    """
    Create a border line of specified width and type
    
    Args:
        width: Width of the border line
        border_type: 'light', 'heavy', or 'double'
        position: 'top', 'bottom', 'middle'
    """
    borders = CLEAN_BORDERS[border_type]
    
    if position == 'top':
        return borders['top_left'] + borders['horizontal'] * (width - 2) + borders['top_right']
    elif position == 'bottom':
        return borders['bottom_left'] + borders['horizontal'] * (width - 2) + borders['bottom_right']
    elif position == 'middle':
        return borders['tee_right'] + borders['horizontal'] * (width - 2) + borders['tee_left']
    else:
        return borders['horizontal'] * width

def create_bordered_content(content: str, width: int, border_type: str = 'light', title: str = None) -> str:
    """
    Create content with clean ASCII borders
    
    Args:
        content: Text content to border
        width: Total width including borders
        border_type: Border style
        title: Optional title for the border
    """
    borders = CLEAN_BORDERS[border_type]
    inner_width = width - 2
    
    lines = []
    
    # Top border with optional title
    if title:
        title_line = f" {title} "
        padding = (inner_width - len(title_line)) // 2
        top_line = borders['top_left'] + borders['horizontal'] * padding + title_line
        top_line += borders['horizontal'] * (inner_width - len(top_line) + 1) + borders['top_right']
        lines.append(top_line)
    else:
        lines.append(create_border_line(width, border_type, 'top'))
    
    # Content lines
    content_lines = content.split('\n') if content else ['']
    for line in content_lines:
        # Truncate or pad line to fit
        if len(line) > inner_width:
            line = line[:inner_width-3] + '...'
        else:
            line = line.ljust(inner_width)
        lines.append(borders['vertical'] + line + borders['vertical'])
    
    # Bottom border
    lines.append(create_border_line(width, border_type, 'bottom'))
    
    return '\n'.join(lines)

def create_app_header(title: str, model: str, width: int) -> str:
    """
    Create a clean application header following Rams design principles
    """
    # Use light borders for the main frame
    borders = CLEAN_BORDERS['light']
    inner_width = width - 2
    
    # Title and model info with intentional spacing
    title_text = f" {title} "
    model_text = f" Model: {model} "
    
    # Calculate spacing
    used_space = len(title_text) + len(model_text)
    remaining = inner_width - used_space
    spacing = '─' * max(0, remaining)
    
    header_content = title_text + spacing + model_text
    
    # Ensure it fits exactly
    if len(header_content) > inner_width:
        header_content = header_content[:inner_width]
    elif len(header_content) < inner_width:
        header_content = header_content.ljust(inner_width, '─')
    
    return borders['top_left'] + header_content + borders['top_right']

def create_section_border(title: str, width: int, border_type: str = 'light') -> str:
    """
    Create a section divider with title
    """
    borders = CLEAN_BORDERS[border_type]
    
    if title:
        title_with_spaces = f" {title} "
        remaining = width - len(title_with_spaces) - 2
        left_dash = remaining // 2
        right_dash = remaining - left_dash
        
        return (borders['tee_right'] + 
                borders['horizontal'] * left_dash + 
                title_with_spaces + 
                borders['horizontal'] * right_dash + 
                borders['tee_left'])
    else:
        return borders['tee_right'] + borders['horizontal'] * (width - 2) + borders['tee_left']

# Minimal loading indicators following "less but better" principle
MINIMAL_LOADING_FRAMES = [
    "   ▪▫▫   ",
    "   ▫▪▫   ", 
    "   ▫▫▪   ",
    "   ▫▪▫   ",
]

DOTS_LOADING = [
    "●○○○",
    "○●○○", 
    "○○●○",
    "○○○●",
    "○○●○",
    "○●○○",
]

# Simple progress indicators
PROGRESS_BARS = {
    'simple': ['▱', '▰'],
    'blocks': ['░', '▓'],
    'dots': ['○', '●']
}