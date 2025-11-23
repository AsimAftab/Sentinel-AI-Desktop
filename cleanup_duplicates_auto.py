#!/usr/bin/env python3
# cleanup_duplicates_auto.py
# Automatically remove duplicate tokens (no confirmation)

import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path
from collections import defaultdict

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Load environment
frontend_env = Path(__file__).parent / "Sentinel-AI-Frontend" / ".env"
if frontend_env.exists():
    load_dotenv(frontend_env)
    print(f"✅ Loaded .env from {frontend_env}")

connection_string = os.getenv("MONGODB_CONNECTION_STRING")
if not connection_string:
    print("❌ MONGODB_CONNECTION_STRING not found")
    sys.exit(1)

print(f"\n🔗 Connecting to MongoDB...")
client = MongoClient(connection_string)
db = client[os.getenv("MONGODB_DATABASE", "sentinel_ai_db")]
tokens = db["service_tokens"]
print(f"✅ Connected to: {db.name} / service_tokens")

# Get all tokens
all_tokens = list(tokens.find({}))
print(f"\n📋 Total tokens: {len(all_tokens)}")

# Group by (service, user_id)
groups = defaultdict(list)
for token in all_tokens:
    key = (token.get('service'), str(token.get('user_id')))
    groups[key].append(token)

# Delete duplicates
deleted_count = 0
for key, token_list in groups.items():
    if len(token_list) > 1:
        service, user_id = key
        print(f"\n⚠️  Found {len(token_list)} duplicates: service={service} user={user_id}")

        # Sort by created_at (newest first)
        token_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        print(f"  → Keeping: {token_list[0]['_id']} (created: {token_list[0].get('created_at')})")

        # Delete older ones
        for old_token in token_list[1:]:
            result = tokens.delete_one({"_id": old_token["_id"]})
            if result.deleted_count > 0:
                deleted_count += 1
                print(f"  ✅ Deleted: {old_token['_id']} (created: {old_token.get('created_at')})")

if deleted_count == 0:
    print("\n✅ No duplicates found - database is clean!")
else:
    print(f"\n✅ Deleted {deleted_count} duplicate(s)")

# Show final state
final_tokens = list(tokens.find({}))
print(f"\n📋 Final state: {len(final_tokens)} token(s)")
for token in final_tokens:
    print(f"  ✅ {token.get('service')} - User: {token.get('user_id')}")

client.close()
print("\n✅ Cleanup complete!")
