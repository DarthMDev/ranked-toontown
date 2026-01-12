"""
Simple script to view MongoDB database contents for Toontown Ranked.
This script connects to the local MongoDB instance and displays the contents of the astrondb database.
"""
import sys
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure

def view_mongodb():
    """Connect to MongoDB and display database contents."""
    try:
        # Connect to MongoDB
        print("Connecting to MongoDB at mongodb://127.0.0.1:27017/...")
        client = MongoClient('mongodb://127.0.0.1:27017/', serverSelectionTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        print("✓ Successfully connected to MongoDB!\n")
        
        # Get the database
        db = client['astrondb']
        
        # List all collections
        collections = db.list_collection_names()
        
        if not collections:
            print("Database 'astrondb' exists but has no collections yet.")
            print("This is normal if you haven't created any toons yet.")
        else:
            print(f"Found {len(collections)} collection(s) in 'astrondb':\n")
            
            for collection_name in collections:
                collection = db[collection_name]
                count = collection.count_documents({})
                print(f"Collection: {collection_name} ({count} document(s))")
                
                # Show first few documents
                if count > 0:
                    print("  Sample documents:")
                    for i, doc in enumerate(collection.find().limit(3)):
                        # Format the document nicely
                        print(f"    Document {i+1}:")
                        for key, value in doc.items():
                            if key == '_id':
                                print(f"      {key}: {value}")
                            elif isinstance(value, (str, int, float, bool, type(None))):
                                # Truncate long strings
                                str_value = str(value)
                                if len(str_value) > 100:
                                    str_value = str_value[:100] + "..."
                                print(f"      {key}: {str_value}")
                            else:
                                print(f"      {key}: <{type(value).__name__}>")
                    if count > 3:
                        print(f"    ... and {count - 3} more document(s)")
                    print()
        
        # Show database stats
        stats = db.command('dbStats')
        print(f"\nDatabase Statistics:")
        print(f"  Collections: {stats.get('collections', 0)}")
        print(f"  Data Size: {stats.get('dataSize', 0):,} bytes")
        print(f"  Storage Size: {stats.get('storageSize', 0):,} bytes")
        
        client.close()
        print("\n✓ Connection closed.")
        
    except ServerSelectionTimeoutError:
        print("✗ Error: Could not connect to MongoDB.")
        print("  Make sure MongoDB is running on 127.0.0.1:27017")
        print("\n  To start MongoDB on Windows:")
        print("    - Check if MongoDB service is running: services.msc")
        print("    - Or run: net start MongoDB")
        print("    - Or manually start: mongod --dbpath <path>")
        sys.exit(1)
    except ConnectionFailure as e:
        print(f"✗ Error: Connection failed - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    print("=" * 60)
    print("Toontown Ranked - MongoDB Database Viewer")
    print("=" * 60)
    print()
    view_mongodb()
