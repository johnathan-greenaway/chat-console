# Using Ollama with Chat Console in WSL

## Overview

Chat Console now intelligently handles Ollama connections, especially for WSL users who run Ollama on their Windows host.

## How It Works

1. **Automatic Detection**: The app checks the configured Ollama URL (default: `http://localhost:11434`)
2. **WSL Auto-Configuration**: In WSL environments, it automatically detects the Windows host IP to connect to Ollama running on Windows
3. **Smart Service Management**: Only attempts to start Ollama locally if:
   - The URL is localhost/127.0.0.1
   - AND Ollama is not already running
4. **Remote URL Support**: If using a non-localhost URL, it won't try to start Ollama locally

## Configuration

### Option 1: Environment Variable
```bash
export OLLAMA_BASE_URL="http://$(ip route show default | awk '{print $3}'):11434"  # For WSL
# or
export OLLAMA_BASE_URL="http://192.168.1.100:11434"  # For remote Ollama
```

### Option 2: Config File
The configuration is stored in `~/.terminalchat/config.json`:
```json
{
  "ollama_base_url": "http://192.168.1.100:11434"
}
```

## WSL Setup

### Running Ollama on Windows Host

1. **Install Ollama on Windows**: Download from https://ollama.ai
2. **Start Ollama on Windows**: It will run on `http://localhost:11434`
3. **Access from WSL**: The app will automatically detect the Windows host IP and connect

### Manual Configuration (if needed)
```bash
# In WSL, set the environment variable
export OLLAMA_BASE_URL="http://$(ip route show default | awk '{print $3}'):11434"

# Or use the Windows host IP directly
export OLLAMA_BASE_URL="http://$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):11434"
```

## Troubleshooting

### Can't connect to Ollama in WSL
1. Ensure Ollama is running on Windows
2. Check Windows Firewall allows connections on port 11434
3. Try using the Windows host IP directly:
   ```bash
   # Get Windows host IP in WSL
   cat /etc/resolv.conf | grep nameserver
   ```

### Connection Refused
- Windows Firewall might be blocking the connection
- Ollama might be bound to localhost only (check Ollama settings)

## Benefits

- **No Duplicate Ollama**: Don't need Ollama in both Windows and WSL
- **Shared Models**: Use the same downloaded models from both environments
- **Better Performance**: Leverage Windows GPU acceleration
- **Automatic Fallback**: If remote Ollama isn't available, helpful error messages guide you