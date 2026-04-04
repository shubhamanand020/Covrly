"""MongoDB database utilities for Covrly."""

import os
from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database

_mongo_client: Optional[MongoClient] = None
_db: Optional[Database] = None

def get_db() -> Database:
    global _mongo_client, _db
    if _db is None:
        mongo_uri = os.environ.get("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI environment variable is not set. Required for MongoDB connection.")
        
        db_name = os.environ.get("COVRLY_DB_NAME", "covrly")
        # Initialize client with timeout settings to fail fast if connection cannot be established
        _mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        _db = _mongo_client[db_name]
        
        # Test the connection to ensure it's valid
        _mongo_client.admin.command('ping')
        print("MongoDB connected successfully")
        
    return _db

def init_mongo_db() -> None:
    """Initialize MongoDB collections and indices."""
    db = get_db()
    
    # users
    db.users.create_index("email", unique=True)
    
    # registration_otps
    db.registration_otps.create_index("expires_at", expireAfterSeconds=0)
    
    # policies
    db.policies.create_index("user_id")
    db.policies.create_index([("user_id", 1), ("policy_type", 1)])
    
    # triggers
    db.triggers.create_index("user_id")
    db.triggers.create_index("timestamp")
    
    # location_snapshots
    db.location_snapshots.create_index("updated_at")
    
    # claims
    db.claims.create_index("user_id")
    db.claims.create_index("status")
