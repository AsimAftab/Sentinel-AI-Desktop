#!/usr/bin/env python3
# delete_old_token.py
# Delete old GMeet token with wrong scopes from database

import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Load environment from Frontend
frontend_env = Path(__file__).parent / "Sentinel-AI-Frontend" / ".env"
if frontend_env.exists():
    load_dotenv(frontend_env)
    print(f"✅ Loaded .env from {frontend_env}")
else:
    print("⚠️ .env file not found, trying system environment...")

connection_string = os.getenv("MONGODB_CONNECTION_STRING")
if not connection_string:
    print("❌ MONGODB_CONNECTION_STRING not found in environment")
    print("\nPlease ensure .env file exists in Sentinel-AI-Frontend/ with:")
    print("MONGODB_CONNECTION_STRING=mongodb+srv://...")
    sys.exit(1)

print(f"\n🔗 Connecting to MongoDB...")
try:
    client = MongoClient(connection_string)
    db_name = os.getenv("MONGODB_DATABASE", "sentinel_ai")
    db = client[db_name]
    tokens = db["tokens"]
    print(f"✅ Connected to database: {db_name}")
except Exception as e:
    print(f"❌ Failed to connect to MongoDB: {e}")
    sys.exit(1)

# Show current tokens
print("\n📋 Current GMeet tokens in database:")
print("-" * 60)
found_tokens = False
for token in tokens.find({"service": "GMeet"}):
    found_tokens = True
    print(f"  Token ID: {token['_id']}")
    print(f"  User ID: {token.get('user_id', 'N/A')}")
    print(f"  Scopes: {token.get('scopes')}")
    print(f"  Created: {token.get('created_at')}")
    print(f"  Encrypted: {token.get('encrypted', False)}")
    print("-" * 60)

if not found_tokens:
    print("  No GMeet tokens found.")
    print("\n✅ Database is clean! You can authenticate with correct scopes now.")
    sys.exit(0)

# Ask for confirmation
print("\n⚠️  These tokens have WRONG scopes (meetings.space.created)")
print("    We need Calendar scopes instead!")
print("\n🗑️  Do you want to delete these tokens? (y/n): ", end='')

try:
    response = input().strip().lower()
except KeyboardInterrupt:
    print("\n\n❌ Cancelled by user.")
    sys.exit(0)

if response != 'y':
    print("❌ Deletion cancelled.")
    print("\nTo re-authenticate with correct scopes:")
    print("1. Delete tokens manually in MongoDB")
    print("2. Or run this script again and confirm deletion")
    sys.exit(0)

# Delete old tokens
print("\n🗑️  Deleting old GMeet tokens...")
try:
    result = tokens.delete_many({"service": "GMeet"})
    print(f"✅ Successfully deleted {result.deleted_count} token(s)")
except Exception as e:
    print(f"❌ Failed to delete tokens: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("✅ DONE! Old tokens deleted.")
print("="*60)
print("\n📋 Next steps:")
print("1. Start frontend: cd Sentinel-AI-Frontend && python main.py")
print("2. Login to your account")
print("3. Go to Dashboard")
print("4. Click 'Connect' button for Google Meet")
print("5. Complete OAuth flow (you'll see Calendar permissions)")
print("6. Token will be saved with CORRECT scopes")
print("7. Test voice command: 'Sentinel, create an instant meeting'")
print("\n🎉 You're all set!")

client.close()
