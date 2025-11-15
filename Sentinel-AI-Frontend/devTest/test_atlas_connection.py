import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.database_config import DatabaseConfig
from pymongo import MongoClient

def test_atlas_connection():
    try:
        config = DatabaseConfig()
        print(f"Connecting to: {config.MONGODB_CONNECTION_STRING[:50]}...")
        
        connection_params = config.get_connection_params()
        client = MongoClient(**connection_params)
        
        # Test ping
        client.admin.command('ping')
        print("[SUCCESS] MongoDB Atlas connection successful!")

        # Test database creation
        db = client[config.MONGODB_DATABASE]
        collection = db[config.MONGODB_COLLECTION_USERS]

        print(f"Database: {config.MONGODB_DATABASE}")
        print(f"Collection: {config.MONGODB_COLLECTION_USERS}")

        client.close()
        return True

    except Exception as e:
        print(f"[ERROR] Atlas connection failed: {e}")
        return False

if __name__ == "__main__":
    test_atlas_connection()