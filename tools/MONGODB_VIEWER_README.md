# Viewing MongoDB Database for Toontown Ranked

This guide explains how to view and interact with the MongoDB database used by Toontown Ranked.

## Prerequisites

1. **MongoDB must be installed and running**
   - On Windows: Check if MongoDB service is running in `services.msc`
   - Or start it manually: `mongod --dbpath <data-directory>`

2. **Connection Details**
   - Host: `127.0.0.1` (localhost)
   - Port: `27017` (default MongoDB port)
   - Database: `astrondb`

## Method 1: Using the Python Script (Recommended)

A simple Python script is provided to view the database:

```bash
python tools/view_mongodb.py
```

This script will:
- Connect to your local MongoDB instance
- List all collections in the `astrondb` database
- Show sample documents from each collection
- Display database statistics

## Method 2: Using MongoDB Compass (GUI)

MongoDB Compass is a graphical tool for viewing and editing MongoDB data.

1. **Download MongoDB Compass**: https://www.mongodb.com/try/download/compass
2. **Install and launch MongoDB Compass**
3. **Connect using**:
   - Connection String: `mongodb://127.0.0.1:27017/`
   - Or use the connection form:
     - Hostname: `127.0.0.1`
     - Port: `27017`
     - Authentication: None (for local development)
4. **Navigate to the `astrondb` database**

## Method 3: Using mongosh (Command Line)

`mongosh` is the MongoDB shell that comes with MongoDB installation.

1. **Open a terminal/command prompt**
2. **Connect to MongoDB**:
   ```bash
   mongosh
   ```
   Or explicitly:
   ```bash
   mongosh mongodb://127.0.0.1:27017/
   ```
3. **Switch to the database**:
   ```javascript
   use astrondb
   ```
4. **List collections**:
   ```javascript
   show collections
   ```
5. **View documents in a collection**:
   ```javascript
   db.<collection_name>.find().pretty()
   ```
   For example:
   ```javascript
   db.objects.find().pretty()
   ```

## Method 4: Using Python Interactively

You can also use Python with pymongo directly:

```python
from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient('mongodb://127.0.0.1:27017/')

# Get the database
db = client['astrondb']

# List collections
print(db.list_collection_names())

# View documents in a collection
for doc in db.objects.find().limit(10):
    print(doc)

# Close connection
client.close()
```

## Troubleshooting

### MongoDB is not running

**Windows:**
- Check services: Open `services.msc` and look for "MongoDB Server"
- Start the service: `net start MongoDB`
- Or start manually: `mongod --dbpath C:\data\db` (or your data directory)

**Linux/Mac:**
- Check if running: `ps aux | grep mongod`
- Start MongoDB: `sudo systemctl start mongod` (Linux) or `brew services start mongodb-community` (Mac)

### Connection refused

- Make sure MongoDB is listening on `127.0.0.1:27017`
- Check MongoDB logs for errors
- Verify firewall isn't blocking the connection

### Database is empty

- This is normal if you haven't created any toons yet
- The database will be populated as you play the game
- Make sure you're using MongoDB backend (not YAML filesystem) for singleplayer

## Notes

- The database name `astrondb` is used by Astron for storing game objects
- Collections are created automatically as needed
- Each toon/object is stored as a document in MongoDB
- When using MongoDB for singleplayer, your data persists between game sessions (unlike YAML filesystem which is session-based)
