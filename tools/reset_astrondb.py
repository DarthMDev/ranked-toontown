"""
Script to reset the astrondb filesystem YAML database.
This will delete all YAML files in the astron/databases/astrondb directory
and also clear the accounts.db file that maps usernames to account IDs.

WARNING: This will permanently delete all data in the astrondb database!
"""

import os
import sys
from pathlib import Path

# Database directory (relative to project root)
DATABASE_DIR = Path(__file__).parent.parent / "astron" / "databases" / "astrondb"
ACCOUNTS_DB_FILE = Path(__file__).parent.parent / "astron" / "databases" / "accounts.db"

def reset_database():
    """Delete all YAML files in the astrondb directory."""
    print("=" * 60)
    print("WARNING: This will PERMANENTLY DELETE ALL DATA in the astrondb database!")
    print("=" * 60)
    print(f"\nDatabase directory: {DATABASE_DIR}")
    
    confirmation = input("\nType 'RESET DATABASE' to confirm: ")
    
    if confirmation != "RESET DATABASE":
        print("Database reset cancelled.")
        return
    
    try:
        # Check if directory exists
        if not DATABASE_DIR.exists():
            print(f"\n✗ Database directory does not exist: {DATABASE_DIR}")
            print("Creating directory...")
            DATABASE_DIR.mkdir(parents=True, exist_ok=True)
            print("Directory created. Database is already empty.")
            return
        
        # Find all YAML files
        yaml_files = list(DATABASE_DIR.glob("*.yaml")) + list(DATABASE_DIR.glob("*.yml"))
        
        if not yaml_files:
            print("\nDatabase is already empty.")
            return
        
        print(f"\nFound {len(yaml_files)} file(s) to delete:")
        for yaml_file in yaml_files:
            print(f"  - {yaml_file.name}")
        
        # Delete all YAML files
        print("\nDeleting files...")
        deleted_count = 0
        for yaml_file in yaml_files:
            try:
                yaml_file.unlink()
                deleted_count += 1
                print(f"  ✓ Deleted {yaml_file.name}")
            except Exception as e:
                print(f"  ✗ Failed to delete {yaml_file.name}: {e}")
        
        # Also clear the accounts.db file if it exists
        print("\nClearing accounts database...")
        accounts_db_files = [
            ACCOUNTS_DB_FILE,
            ACCOUNTS_DB_FILE.with_suffix('.db.dir'),
            ACCOUNTS_DB_FILE.with_suffix('.db.dat'),
            ACCOUNTS_DB_FILE.with_suffix('.db.bak'),
        ]
        
        accounts_deleted = 0
        for db_file in accounts_db_files:
            if db_file.exists():
                try:
                    db_file.unlink()
                    accounts_deleted += 1
                    print(f"  ✓ Deleted {db_file.name}")
                except Exception as e:
                    print(f"  ✗ Failed to delete {db_file.name}: {e}")
        
        if accounts_deleted == 0:
            print("  (No accounts database files found)")
        
        print(f"\n✓ Database reset complete!")
        print(f"Deleted {deleted_count} out of {len(yaml_files)} YAML file(s).")
        print(f"Deleted {accounts_deleted} accounts database file(s).")
        
    except Exception as e:
        print(f"\n✗ Error resetting database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    reset_database()
