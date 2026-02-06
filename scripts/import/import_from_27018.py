#!/usr/bin/env python3

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import sys

SOURCE_URI = "mongodb://localhost:27018"
TARGET_URI = "mongodb://localhost:27019"
DB_NAME = "kessler"
COLLECTION_NAME = "satellites"

def import_collection():
    try:
        print(f"Connecting to source MongoDB at {SOURCE_URI}...")
        source_client = MongoClient(SOURCE_URI, serverSelectionTimeoutMS=5000)
        source_client.admin.command('ping')
        source_db = source_client[DB_NAME]
        source_collection = source_db[COLLECTION_NAME]
        
        print(f"Connecting to target MongoDB at {TARGET_URI}...")
        target_client = MongoClient(TARGET_URI, serverSelectionTimeoutMS=5000)
        target_client.admin.command('ping')
        target_db = target_client[DB_NAME]
        target_collection = target_db[COLLECTION_NAME]
        
        count = source_collection.count_documents({})
        print(f"Found {count} documents in source collection")
        
        if count == 0:
            print("Source collection is empty. Nothing to import.")
            return
        
        print(f"Importing documents from {SOURCE_URI}/{DB_NAME}/{COLLECTION_NAME}")
        print(f"              to {TARGET_URI}/{DB_NAME}/{COLLECTION_NAME}")
        
        documents = list(source_collection.find({}))
        
        if documents:
            for doc in documents:
                if '_id' in doc:
                    del doc['_id']
            
            result = target_collection.insert_many(documents, ordered=False)
            print(f"✓ Successfully imported {len(result.inserted_ids)} documents")
        
        final_count = target_collection.count_documents({})
        print(f"Target collection now has {final_count} documents")
        
        source_client.close()
        target_client.close()
        
    except ConnectionFailure as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error during import: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import_collection()
