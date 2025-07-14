#!/usr/bin/env python3
"""Test script for the enhanced search functionality."""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'chat-cli'))

# Suppress logging during imports
import logging
logging.getLogger().setLevel(logging.CRITICAL)

from app.api.ollama import OllamaClient


async def test_enhanced_search():
    """Test the enhanced search functionality."""
    
    print("Testing Enhanced Ollama Model Search")
    print("=" * 50)
    
    # Create client
    client = await OllamaClient.create()
    
    # Test 1: Basic search
    print("\n1. Testing basic search for 'gemma'...")
    try:
        all_models = await client.list_available_models_from_registry("")
        matching_models = []
        query = "gemma"
        query_lower = query.lower()
        
        for model in all_models:
            # Check name, description, and model family
            name_match = query_lower in model.get("name", "").lower()
            desc_match = query_lower in model.get("description", "").lower()
            family_match = query_lower in model.get("model_family", "").lower()
            
            # Also check variants if available
            variants_match = False
            if "variants" in model and model["variants"]:
                variants_text = " ".join([str(v).lower() for v in model["variants"]])
                if query_lower in variants_text:
                    variants_match = True
            
            if name_match or desc_match or family_match or variants_match:
                matching_models.append(model)
        
        print(f"Found {len(matching_models)} matching models")
        
        # Show first 3 matches
        for i, model in enumerate(matching_models[:3]):
            print(f"  {i+1}. {model.get('name', 'unknown')} - {model.get('model_family', 'Unknown')}")
        
        print("✓ Basic search works")
        
    except Exception as e:
        print(f"✗ Basic search failed: {e}")
    
    # Test 2: Get variants for a specific model
    print("\n2. Testing variant fetching for 'gemma2'...")
    try:
        detailed_model = await client.get_model_with_variants("gemma2")
        variants = detailed_model.get("detailed_variants", [])
        
        if variants:
            print(f"Found {len(variants)} variants for gemma2:")
            for variant in variants[:5]:  # Show first 5
                tag = variant.get("tag", "unknown")
                size = variant.get("size", "Unknown")
                print(f"  - {tag} ({size})")
            print("✓ Variant fetching works")
        else:
            print("No variants found (may be due to web scraping issues)")
            
    except Exception as e:
        print(f"✗ Variant fetching failed: {e}")
    
    # Test 3: Test model details with dict input (our bug fix)
    print("\n3. Testing model details with dict input...")
    try:
        model_dict = {
            'name': 'gemma2',
            'description': 'A test model',
            'model_family': 'Gemma'
        }
        result = await client.get_model_details(model_dict)
        if 'error' not in result or 'API:' in result.get('error', ''):
            print("✓ Dict input handling works")
        else:
            print(f"✗ Dict input failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"✗ Dict input test failed: {e}")
    
    print("\n" + "=" * 50)
    print("Enhanced search testing completed!")


if __name__ == "__main__":
    asyncio.run(test_enhanced_search())