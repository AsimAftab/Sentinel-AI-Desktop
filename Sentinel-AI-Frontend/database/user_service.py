from pymongo import MongoClient
from datetime import datetime
import bcrypt
from config.database_config import DatabaseConfig

class UserService:
    def __init__(self):
        self.config = DatabaseConfig()
    
    def save_user(self, username, fullname, phone, email, password):
        client = None
        try:
            connection_params = self.config.get_connection_params()
            client = MongoClient(**connection_params)
            
            db = client[self.config.MONGODB_DATABASE]
            users_collection = db[self.config.MONGODB_COLLECTION_USERS]
            
            # Check if user already exists
            if users_collection.find_one({"username": username}):
                return False, "Username already exists in database"
            
            # Hash password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            user_doc = {
                'username': username,
                'fullname': fullname,
                'phone': phone,
                'email': email,
                'password': hashed_password,
                'created_at': datetime.utcnow(),
                'is_active': True,
                'last_login': None
            }
            
            result = users_collection.insert_one(user_doc)
            
            return True, f"User saved successfully with ID: {result.inserted_id}"

        except Exception as e:
            return False, f"Database error: {str(e)}"
        finally:
            if client:
                client.close()

    def get_user_by_username(self, username):
        """Get user document from MongoDB by username (includes _id)"""
        client = None
        try:
            connection_params = self.config.get_connection_params()
            client = MongoClient(**connection_params)

            db = client[self.config.MONGODB_DATABASE]
            users_collection = db[self.config.MONGODB_COLLECTION_USERS]

            user = users_collection.find_one({"username": username})
            return user  # Returns None if not found, or full user document with _id

        except Exception as e:
            print(f"Error fetching user: {e}")
            return None
        finally:
            if client:
                client.close()