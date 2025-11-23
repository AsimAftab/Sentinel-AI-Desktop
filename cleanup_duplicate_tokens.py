#!/usr/bin/env python3
# cleanup_duplicate_tokens.py
# Remove duplicate tokens from MongoDB - keep only the most recent one per user+service

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
    db_name = os.getenv("MONGODB_DATABASE", "sentinel_ai_db")
    db = client[db_name]
    tokens = db["service_tokens"]
    print(f"✅ Connected to database: {db_name}")
    print(f"✅ Using collection: service_tokens")
except Exception as e:
    print(f"❌ Failed to connect to MongoDB: {e}")
    sys.exit(1)

# Show current tokens
print("\n📋 Current tokens in database:")
print("-" * 80)
all_tokens = list(tokens.find({}))
print(f"Total tokens: {len(all_tokens)}\n")

for token in all_tokens:
    print(f"  ID: {token['_id']}")
    print(f"  Service: {token.get('service', 'N/A')}")
    print(f"  User ID: {token.get('user_id', 'N/A')}")
    print(f"  Created: {token.get('created_at', 'N/A')}")
    print(f"  Updated: {token.get('updated_at', 'N/A')}")
    print("-" * 80)

# Find duplicates (same service + user_id)
print("\n🔍 Checking for duplicates...")
duplicates_found = False

# Group by (service, user_id)
from collections import defaultdict
groups = defaultdict(list)

for token in all_tokens:
    key = (token.get('service'), str(token.get('user_id')))
    groups[key].append(token)

# Find groups with duplicates
for key, token_list in groups.items():
    if len(token_list) > 1:
        duplicates_found = True
        service, user_id = key
        print(f"\n⚠️  Found {len(token_list)} duplicates for service={service} user_id={user_id}")

        # Sort by created_at (newest first)
        token_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        print(f"  → Keeping newest: {token_list[0]['_id']} (created: {token_list[0].get('created_at')})")
        print(f"  → Will delete {len(token_list)-1} older token(s):")
        for old_token in token_list[1:]:
            print(f"     - {old_token['_id']} (created: {old_token.get('created_at')})")

if not duplicates_found:
    print("  ✅ No duplicates found!")
    print("\n✅ Database is clean!")
    client.close()
    sys.exit(0)

# Ask for confirmation
print("\n" + "=" * 80)
print("⚠️  DELETE DUPLICATES?")
print("=" * 80)
print("This will remove older duplicate tokens, keeping only the newest one per service+user.")
print("\nType 'yes' to proceed, anything else to cancel: ", end='')

try:
    response = input().strip().lower()
except KeyboardInterrupt:
    print("\n\n❌ Cancelled by user.")
    client.close()
    sys.exit(0)

if response != 'yes':
    print("❌ Deletion cancelled.")
    client.close()
    sys.exit(0)

# Delete duplicates
print("\n🗑️  Deleting duplicate tokens...")
deleted_count = 0

for key, token_list in groups.items():
    if len(token_list) > 1:
        # Sort by created_at (newest first)
        token_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        # Delete all except the newest
        for old_token in token_list[1:]:
            try:
                result = tokens.delete_one({"_id": old_token["_id"]})
                if result.deleted_count > 0:
                    deleted_count += 1
                    print(f"  ✅ Deleted: {old_token['_id']}")
            except Exception as e:
                print(f"  ❌ Failed to delete {old_token['_id']}: {e}")

print(f"\n✅ Deleted {deleted_count} duplicate token(s)")

# Show final state
print("\n📋 Final token state:")
print("-" * 80)
final_tokens = list(tokens.find({}))
print(f"Total tokens: {len(final_tokens)}\n")

for token in final_tokens:
    print(f"  Service: {token.get('service')}, User: {token.get('user_id')}, Created: {token.get('created_at')}")

print("\n" + "=" * 80)
print("✅ CLEANUP COMPLETE!")
print("=" * 80)

client.close()
