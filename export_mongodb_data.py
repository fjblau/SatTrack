#!/usr/bin/env python3
"""
Export all satellite data from MongoDB to JSON file for migration to ArangoDB.
"""
import json
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
import os

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27019")
DB_NAME = "kessler"
COLLECTION_NAME = "satellites"

def json_serializer(obj):
    """Custom JSON serializer for MongoDB objects"""
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def export_data():
    """Export MongoDB data to JSON file"""
    print("Connecting to MongoDB...")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    
    try:
        # Test connection
        client.admin.command('ping')
        print(f"✓ Connected to MongoDB: {MONGO_URI}")
        
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        # Count documents
        count = collection.count_documents({})
        print(f"Found {count:,} documents in {DB_NAME}.{COLLECTION_NAME}")
        
        if count == 0:
            print("No data to export!")
            return
        
        # Export all documents
        print("Exporting documents...")
        documents = list(collection.find({}))
        
        # Convert ObjectId to string for JSON serialization
        for doc in documents:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
        
        # Save to JSON file
        output_file = "mongodb_export.json"
        with open(output_file, 'w') as f:
            json.dump(documents, f, indent=2, default=json_serializer)
        
        print(f"✓ Exported {len(documents):,} documents to {output_file}")
        
        # Print some statistics
        print("\nExport Statistics:")
        print(f"  Total documents: {len(documents):,}")
        
        # Sample first document structure
        if documents:
            print("\nSample document structure:")
            sample = documents[0]
            print(f"  identifier: {sample.get('identifier', 'N/A')}")
            print(f"  sources: {list(sample.get('sources', {}).keys())}")
            print(f"  canonical fields: {len(sample.get('canonical', {}))}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        client.close()
    
    return True

if __name__ == "__main__":
    success = export_data()
    exit(0 if success else 1)
