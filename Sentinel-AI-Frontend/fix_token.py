#!/usr/bin/env python3
"""
Quick fix script to delete corrupted token.json
Run this if you encounter token corruption errors.
"""

import os
import sys

def fix_token():
    """Delete corrupted token.json file."""
    token_path = os.path.join(os.path.dirname(__file__), 'token.json')

    if os.path.exists(token_path):
        try:
            os.remove(token_path)
            print(f"✅ Deleted corrupted token file: {token_path}")
            print("\nNext steps:")
            print("1. Run the application: python launcher.py")
            print("2. Click 'Connect' on GMeet service")
            print("3. Complete OAuth in browser")
            print("4. New valid token will be created")
            return True
        except Exception as e:
            print(f"❌ Failed to delete token file: {e}")
            print(f"\nPlease manually delete: {token_path}")
            return False
    else:
        print(f"ℹ️  No token file found at: {token_path}")
        print("This is normal if you haven't connected GMeet yet.")
        return True

if __name__ == "__main__":
    print("=" * 60)
    print("Sentinel AI - Token Corruption Fix")
    print("=" * 60)
    print()

    success = fix_token()

    print()
    print("=" * 60)
    sys.exit(0 if success else 1)
