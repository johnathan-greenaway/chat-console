# Custom Provider Integration Guide

Chat-console now supports OpenAI-compatible drop-in replacements through a flexible custom provider system. This guide explains how to configure and use OpenAI-compatible APIs including Uplink Worker, Groq, and other compatible services.

## Quick Setup for OpenAI-Compatible APIs

### 1. Set your API key
```bash
export OPENAI_COMPATIBLE_API_KEY="your-api-key-here"
```

### 2. Optional: Customize base URL
```bash
export OPENAI_COMPATIBLE_BASE_URL="https://your-custom-endpoint.workers.dev/v1"
```

### 3. Run chat-console
```bash
chat-console
# or
c-c
```

### 4. Select provider and models
1. Choose "OpenAI Compatible API" from the Provider dropdown
2. Select from available models:
- **Qwen 3 32B** (Reasoning & Code) - `qwen/qwen3-32b`
- **Qwen 2.5 Coder 32B** - `qwen2.5-coder-32b-instruct`
- **Llama 3.3 70B Versatile** - `llama-3.3-70b-versatile`
- **Llama 3.2 90B Vision** - `llama-3.2-90b-vision-preview`
- **DeepSeek R1 Lite** - `deepseek-r1-lite-preview`
- And more!

## Adding Other OpenAI-Compatible Providers

### Step 1: Configure Environment Variables

For each new provider, set the required environment variables:

```bash
# Example for a hypothetical "SuperAI" provider
export SUPERAI_API_KEY="your-super-ai-key"
export SUPERAI_BASE_URL="https://api.superai.com/v1"
```

### Step 2: Add Provider Configuration

Edit `chat-cli/app/config.py` and add your provider to `CUSTOM_PROVIDERS`:

```python
CUSTOM_PROVIDERS = {
    "uplink": {
        "base_url": os.getenv("CUSTOM_API_BASE_URL", "https://api.example.com/v1"),
        "api_key": os.getenv("UPLINK_API_KEY", ""),
        "type": "openai_compatible"
    },
    "superai": {  # Add your new provider
        "base_url": os.getenv("SUPERAI_BASE_URL", "https://api.superai.com/v1"),
        "api_key": os.getenv("SUPERAI_API_KEY", ""),
        "type": "openai_compatible"
    }
}
```

### Step 3: Add Models to Configuration

Add your provider's models to the `DEFAULT_CONFIG["available_models"]` section:

```python
# Add after existing Uplink models
"superai-gpt-4": {
    "provider": "superai",
    "max_tokens": 8192,
    "display_name": "SuperAI GPT-4"
},
"superai-claude-like": {
    "provider": "superai",
    "max_tokens": 16384,
    "display_name": "SuperAI Claude-like Model"
},
```

## Supported Features

### All OpenAI-Compatible Features
- ✅ Chat completions (`/v1/chat/completions`)
- ✅ Streaming responses
- ✅ Temperature and max_tokens control
- ✅ System messages and conversation history
- ✅ Model listing (`/v1/models`)

### Advanced Features (if supported by provider)
- ✅ Function/tool calling
- ✅ Vision models (multimodal)
- ✅ JSON mode
- ✅ Reasoning modes
- ✅ Custom parameters

### Response Styles
All custom providers support chat-console's response styles:
- **Default**: Standard responses
- **Concise**: Brief, to-the-point
- **Detailed**: Comprehensive explanations
- **Technical**: Precise technical language
- **Friendly**: Conversational tone

## Testing Your Integration

Run the included test script:

```bash
python test_uplink_integration.py
```

This will verify:
- ✅ API key configuration
- ✅ Provider availability
- ✅ Model listing
- ✅ Client creation
- ✅ Basic completion (if API key is valid)

## Troubleshooting

### Common Issues

#### API Key Not Found
```
❌ Provider 'uplink' is not available. Please check your configuration.
```
**Solution:** Set the API key environment variable:
```bash
export UPLINK_API_KEY="your-key-here"
```

#### Connection Errors
```
Custom provider streaming error: Connection timeout
```
**Solutions:**
- Check base URL is correct
- Verify network connectivity
- Ensure API endpoint is accessible

#### Model Not Found
```
❌ Model 'custom-model' not found
```
**Solutions:**
- Check model ID spelling
- Verify model is available in provider's `/v1/models` endpoint
- Add model to config if using custom model names

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
# Set debug environment variable
export CHAT_DEBUG=1

# Run with verbose output
chat-console --debug
```

## Environment Variables Reference

### Uplink Worker
```bash
UPLINK_API_KEY="your-api-key"                    # Required
UPLINK_BASE_URL="https://your-endpoint/v1"       # Optional
```

### Generic OpenAI-Compatible Provider
```bash
PROVIDER_NAME_API_KEY="your-key"                 # Required
PROVIDER_NAME_BASE_URL="https://api.provider/v1" # Required
```

## Configuration Examples

### Local OpenAI-Compatible Server
```python
"local_server": {
    "base_url": os.getenv("LOCAL_SERVER_BASE_URL", "http://localhost:8000/v1"),
    "api_key": os.getenv("LOCAL_SERVER_API_KEY", "local-key"),
    "type": "openai_compatible"
}
```

### Corporate API Gateway
```python
"corporate": {
    "base_url": os.getenv("CORPORATE_BASE_URL", "https://ai-gateway.corp.com/v1"),
    "api_key": os.getenv("CORPORATE_API_KEY", ""),
    "type": "openai_compatible"
}
```

### Multiple Provider Setup
```bash
# Set up multiple providers
export UPLINK_API_KEY="uplink-key"
export GROQ_API_KEY="groq-key"
export GROQ_BASE_URL="https://api.groq.com/openai/v1"
export LOCAL_LLM_API_KEY="local"
export LOCAL_LLM_BASE_URL="http://localhost:8000/v1"

# Run chat-console with all providers available
chat-console
```

## Best Practices

### API Key Management
- Use environment variables, never hardcode keys
- Consider using `.env` files for development
- Rotate keys regularly for production use

### Performance Optimization
- Use appropriate temperature settings (0.1-0.3 for code, 0.7-0.9 for creative)
- Set reasonable max_tokens limits
- Enable streaming for better UX

### Model Selection
- **For Code**: Qwen Coder models, CodeLlama
- **For Reasoning**: Qwen 3, DeepSeek R1
- **For Vision**: Llama Vision models
- **For Speed**: Smaller parameter models (7B-14B)
- **For Quality**: Larger parameter models (32B-70B)

## Integration with Continue.dev and Cursor

Your configured providers can also be used with other tools:

### Continue.dev
```json
{
  "models": [
    {
      "title": "Qwen Coder via Uplink",
      "provider": "openai", 
      "model": "qwen2.5-coder-32b-instruct",
      "apiBase": "https://api.example.com/v1",
      "apiKey": "your-uplink-key"
    }
  ]
}
```

### Cursor IDE
1. Settings → AI Providers
2. Add OpenAI Compatible Provider
3. Base URL: `https://api.example.com/v1`
4. API Key: Your Uplink key
5. Model: `qwen2.5-coder-32b-instruct`

## Contributing

To add support for new OpenAI-compatible providers:

1. Add provider configuration to `CUSTOM_PROVIDERS`
2. Add models to `DEFAULT_CONFIG["available_models"]`
3. Test with the integration test script
4. Update this documentation

## Support

For issues with:
- **Chat-console integration**: Create an issue in the chat-console repo
- **Uplink Worker**: Contact the Uplink Worker support
- **Other providers**: Contact the respective provider support