#!/usr/bin/env python3
"""
Quick test script to verify authentication is working
"""
import os
from dotenv import load_dotenv
from token_minter import get_user_token_minter

load_dotenv()

print("Testing authentication methods...\n")

# Check environment variables
print("Environment variables:")
print(f"  DATABRICKS_HOST: {os.getenv('DATABRICKS_HOST')}")
print(f"  DATABRICKS_TOKEN: {'Set' if os.getenv('DATABRICKS_TOKEN') else 'Not set'}")
print(f"  DATABRICKS_CLIENT_ID: {'Set' if os.getenv('DATABRICKS_CLIENT_ID') else 'Not set'}")
print(f"  DATABRICKS_CLIENT_SECRET: {'Set' if os.getenv('DATABRICKS_CLIENT_SECRET') else 'Not set'}")
print()

# Try to get a token
try:
    token_minter = get_user_token_minter()
    token = token_minter.get_token()
    print("✓ Successfully obtained authentication token!")
    print(f"  Token preview: {token[:20]}..." if len(token) > 20 else f"  Token: {token}")
except Exception as e:
    print(f"✗ Failed to obtain token: {str(e)}")
    print("\nTo fix this, add one of the following to your .env file:")
    print("  1. DATABRICKS_TOKEN=your-personal-access-token")
    print("  2. DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET (OAuth)")
