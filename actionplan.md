# Pure Console Feature Parity Action Plan
**Date:** 2025-06-28  
**Status:** Ready for Implementation

## Overview
This document outlines the implementation plan to achieve feature parity between the pure console version (`console_chat.py`) and the Textual UI version (`app/main.py`) of Chat Console.

## Current Status
The pure console version has basic chat functionality but lacks several key features present in the Textual version. Based on analysis, here are the major gaps:

### ✅ Already Implemented
- Basic chat interface with ASCII borders
- Message history and conversation management
- Basic model selection
- Simple streaming responses
- Keyboard shortcuts (q, n, h, s)
- Database integration

### ❌ Missing Features (Priority Order)

## Phase 1: Easy Wins (2-4 hours)
*Features that can be implemented quickly with high impact*

### 1.1 Enhanced Settings Management
**File:** `console_chat.py` - `show_settings()` method
**Missing:** Style selection, settings persistence
```python
# Add to show_settings():
# - Style selection menu similar to model selection
# - Save settings to config file using save_settings_to_config()
# - Load saved settings on startup
```

### 1.2 Improved Cancellation Handling
**File:** `console_chat.py` - `get_input()` and `generate_response()` methods
**Missing:** Proper async cancellation, cleanup on Ctrl+C
```python
# Enhance Ctrl+C handling:
# - Cancel streaming requests properly
# - Clean up incomplete assistant messages
# - Reset generation state correctly
```

## Phase 2: Medium Impact (4-8 hours)
*Features requiring moderate development effort*

### 2.1 Auto Title Generation ⭐ HIGH IMPACT
**Files:** `console_chat.py` - new method, `app/utils.py` integration
**Missing:** Background title generation for first messages
```python
# Implementation approach:
# 1. Import generate_conversation_title from utils.py
# 2. Add _generate_title_background() method similar to Textual version
# 3. Call after first user message
# 4. Handle provider selection (OpenAI > Anthropic > Ollama small models)
# 5. Update conversation title in UI and database
```

### 2.2 Enhanced Streaming Implementation
**Files:** `console_chat.py` - `generate_response()`, `app/console_utils.py`
**Missing:** Provider-specific optimizations, better real-time updates
```python
# Improvements needed:
# 1. Add provider-specific streaming logic
# 2. Implement update intervals (every 0.1s instead of per chunk)
# 3. Add loading indicators for different model types
# 4. Better error handling during streaming
```

### 2.3 Advanced Message Formatting
**File:** `console_chat.py` - `format_message()` method
**Missing:** Code syntax highlighting, better word wrapping
```python
# Add features:
# 1. Basic code block detection and highlighting using colorama
# 2. Improved word wrapping for long lines
# 3. Better timestamp and role formatting
# 4. Support for CONFIG["highlight_code"] setting
```

## Phase 3: High Complexity (8-16 hours)
*Major features requiring significant development*

### 3.1 Ollama Model Browser ⭐ MAJOR FEATURE
**File:** `console_chat.py` - new methods and UI screens
**Missing:** Complete model management functionality
```python
# Implementation approach:
# 1. Add show_model_browser() method with text-based interface
# 2. Create model listing with available/local tabs
# 3. Add model details view (name, size, modified date)
# 4. Implement model pull/download with progress
# 5. Add model deletion functionality
# 6. Integrate with existing 'm' key binding
```

**Sub-tasks:**
- Model discovery and listing
- Model download with progress indicators
- Model deletion confirmation
- Model switching interface
- Error handling for model operations

### 3.2 Advanced Settings Panel
**File:** `console_chat.py` - enhanced `show_settings()` method
**Missing:** Comprehensive configuration management
```python
# Features to add:
# 1. Model preloading settings
# 2. Ollama connection settings
# 3. Dynamic title generation toggle
# 4. Syntax highlighting toggle
# 5. History limits and cleanup
# 6. Export/import settings
```

## Implementation Strategy

### Quick Start (Phase 1)
1. **Settings Persistence** - Modify `show_settings()` to save selections
2. **Style Selection** - Add style menu similar to model selection
3. **Better Cancellation** - Improve Ctrl+C handling

### Medium Term (Phase 2)
1. **Auto Titles** - Import and adapt title generation from utils.py
2. **Streaming Improvements** - Add provider-specific logic
3. **Message Formatting** - Add basic syntax highlighting

### Long Term (Phase 3)
1. **Model Browser** - Design text-based model management interface
2. **Advanced Settings** - Comprehensive configuration panel

## Development Guidelines

### Code Style
- Follow existing ASCII art and borders pattern from `app/ui/borders.py`
- Maintain clean, minimal UI following Dieter Rams principles
- Use consistent error handling and user notifications
- Preserve existing keyboard shortcuts and add new ones logically

### Testing Approach
- Test with all three providers (OpenAI, Anthropic, Ollama)
- Verify settings persistence across restarts
- Test cancellation during streaming
- Validate model browser operations

### Dependencies
- No new dependencies should be added
- Reuse existing utility functions from `app/` modules
- Maintain compatibility with current console_utils.py

## File Structure Impact

### New Files Needed
None - all functionality should be added to existing files

### Files to Modify
1. `console_chat.py` - Main implementation
2. `app/console_utils.py` - Shared utilities (if needed)
3. `CLAUDE.md` - Update with new features

### Key Integration Points
- `app/utils.py` - Title generation, model resolution
- `app/config.py` - Settings persistence
- `app/api/` - Provider-specific implementations
- `app/database.py` - Conversation management

## Success Criteria

### Phase 1 Complete When:
- [ ] Settings persist between sessions
- [ ] Style selection works in console
- [ ] Ctrl+C properly cancels generation

### Phase 2 Complete When:
- [ ] Auto title generation works for first messages
- [ ] Streaming shows real-time updates smoothly
- [ ] Code blocks are highlighted in console

### Phase 3 Complete When:
- [ ] Model browser can list, download, and delete models
- [ ] Advanced settings panel manages all configuration
- [ ] Feature parity achieved with Textual version

## Estimated Timeline
- **Phase 1:** 2-4 hours (1 developer day)
- **Phase 2:** 4-8 hours (1-2 developer days)  
- **Phase 3:** 8-16 hours (2-4 developer days)
- **Total:** 14-28 hours (3-7 developer days)

## Risk Assessment
- **Low Risk:** Phases 1 & 2 - well-defined APIs exist
- **Medium Risk:** Phase 3 Model Browser - complex UI in console
- **Mitigation:** Implement in phases, test frequently

---
*This action plan provides a clear roadmap for achieving feature parity while maintaining the console version's simplicity and performance advantages.*