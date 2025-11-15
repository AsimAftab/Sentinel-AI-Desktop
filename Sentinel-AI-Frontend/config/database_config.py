import os
from dotenv import load_dotenv

load_dotenv()

class DatabaseConfig:
    # MongoDB Settings
    MONGODB_CONNECTION_STRING = os.getenv('MONGODB_CONNECTION_STRING', 'mongodb://localhost:27017/')
    MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'sentinel_ai_db')
    MONGODB_COLLECTION_USERS = os.getenv('MONGODB_COLLECTION_USERS', 'users')
    MONGODB_COLLECTION_TOKENS = os.getenv('MONGODB_COLLECTION_TOKENS', 'service_tokens')
    
    # Connection Pool Settings
    MONGODB_MAX_POOL_SIZE = int(os.getenv('MONGODB_MAX_POOL_SIZE', '10'))
    MONGODB_CONNECT_TIMEOUT = int(os.getenv('MONGODB_CONNECT_TIMEOUT', '10000'))
    
    @classmethod
    def get_connection_params(cls):
        return {
            'host': cls.MONGODB_CONNECTION_STRING,
            'maxPoolSize': cls.MONGODB_MAX_POOL_SIZE,
            'connectTimeoutMS': cls.MONGODB_CONNECT_TIMEOUT,
            'serverSelectionTimeoutMS': 5000
        }