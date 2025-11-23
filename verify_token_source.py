#!/usr/bin/env python3
# verify_token_source.py
# Verify that backend is reading tokens from MongoDB

import sys
import os
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add backend to path
backend_path = Path(__file__).parent / "Sentinel-AI-Backend"
sys.path.insert(0, str(backend_path))

# Load backend .env
from dotenv import load_dotenv
load_dotenv(backend_path / ".env")

print("=" * 80)
print("🔍 TOKEN SOURCE VERIFICATION")
print("=" * 80)

# Check backend .env configuration
print("\n📋 Backend Configuration:")
print(f"  MONGODB_CONNECTION_STRING: {'✅ SET' if os.getenv('MONGODB_CONNECTION_STRING') else '❌ NOT SET'}")
print(f"  MONGODB_DATABASE: {os.getenv('MONGODB_DATABASE', 'NOT SET')}")
print(f"  MONGODB_COLLECTION_TOKENS: {os.getenv('MONGODB_COLLECTION_TOKENS', 'NOT SET')}")

# Import TokenManager
from src.utils.token_manager import get_token_manager

print("\n🔧 Initializing TokenManager...")
tm = get_token_manager()

print(f"\n✅ TokenManager Status:")
print(f"  MongoDB Available: {tm.mongodb_available}")
print(f"  Database Name: {tm.db.name if tm.db is not None else 'N/A'}")
print(f"  Collection Name: {tm.tokens_collection.name if tm.tokens_collection is not None else 'N/A'}")

# Try to get user context
print("\n📂 Checking User Context...")
user_id = tm.get_user_id_from_context()
print(f"  Current User ID: {user_id}")

if user_id:
    # Try to get token from database
    print("\n🔍 Attempting to retrieve token from MongoDB...")
    token_dict = tm.get_token_from_db("GMeet", user_id)

    if token_dict:
        print("  ✅ TOKEN FOUND IN MONGODB!")
        print(f"  ✅ Token has refresh_token: {bool(token_dict.get('refresh_token'))}")
        print(f"  ✅ Token has access_token: {bool(token_dict.get('token'))}")
        print(f"  ✅ Scopes: {token_dict.get('scopes', [])}")

        # Try to build credentials
        print("\n🔧 Testing credential creation...")
        creds = tm.get_calendar_credentials(user_id)

        if creds:
            print("  ✅ CREDENTIALS CREATED SUCCESSFULLY!")
            print(f"  ✅ Valid: {creds.valid}")
            print(f"  ✅ Expired: {creds.expired}")
            print(f"  ✅ Has refresh token: {bool(creds.refresh_token)}")
        else:
            print("  ❌ Failed to create credentials")
    else:
        print("  ❌ No token found in MongoDB")
        print("\n💡 Checking fallback locations...")

        # Check file paths
        token_paths = [
            backend_path / "token.json",
            backend_path.parent / "Sentinel-AI-Frontend" / "token.json",
        ]

        for path in token_paths:
            if path.exists():
                print(f"  ⚠️  Found token.json at: {path}")
                print("  ⚠️  Backend is using FILE fallback, not MongoDB!")
            else:
                print(f"  ✅ No token.json at: {path}")
else:
    print("  ❌ No user context found")

print("\n" + "=" * 80)
print("🎯 CONCLUSION:")
print("=" * 80)

if tm.mongodb_available and user_id and token_dict:
    print("✅ Backend is successfully reading tokens from MongoDB!")
    print("✅ Database: sentinel_ai_db")
    print("✅ Collection: service_tokens")
    print("✅ User ID linked: " + str(user_id))
    print("\n🎉 FULLY INTEGRATED!")
else:
    print("❌ Backend is NOT reading from MongoDB")
    print("💡 Check:")
    if not tm.mongodb_available:
        print("  - MongoDB connection")
    if not user_id:
        print("  - user_context.json file")
    if not token_dict:
        print("  - Token in database for this user")

print("=" * 80)
