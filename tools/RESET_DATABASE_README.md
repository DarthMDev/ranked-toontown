# Database Reset Instructions

This document explains how to reset the astrondb filesystem YAML database.

## Option 1: Using the Python Script (Recommended)

1. Make sure the server is stopped (Astron should not be running).

2. Run the reset script:
   ```bash
   python tools/reset_astrondb.py
   ```

3. Type `RESET DATABASE` when prompted to confirm.

The script will delete all `.yaml` and `.yml` files in the `astron/databases/astrondb` directory, and also clear the `accounts.db` file that maps usernames to account IDs.

## Option 2: Manual Deletion

1. Make sure the server is stopped (Astron should not be running).

2. Navigate to the database directory:
   ```bash
   cd astron/databases
   ```

3. Delete all YAML files in the astrondb directory:
   - **Windows (PowerShell):**
     ```powershell
     Remove-Item astrondb\*.yaml, astrondb\*.yml
     ```
   - **Windows (CMD):**
     ```cmd
     del astrondb\*.yaml astrondb\*.yml
     ```
   - **Linux/Mac:**
     ```bash
     rm astrondb/*.yaml astrondb/*.yml
     ```

4. Delete the accounts database files:
   - **Windows (PowerShell):**
     ```powershell
     Remove-Item accounts.db*
     ```
   - **Windows (CMD):**
     ```cmd
     del accounts.db*
     ```
   - **Linux/Mac:**
     ```bash
     rm accounts.db*
     ```

## Option 3: Delete the Entire Directory

If you want to completely remove the database directory:

1. Make sure the server is stopped.

2. Delete the directory:
   - **Windows:**
     ```powershell
     Remove-Item -Recurse -Force astron\databases\astrondb
     ```
   - **Linux/Mac:**
     ```bash
     rm -rf astron/databases/astrondb
     ```

3. The directory will be recreated automatically when Astron starts.

## Important Notes

- **BACKUP FIRST**: If you have any important data, make sure to back it up before resetting!
- **STOP THE SERVER**: Always stop Astron before deleting database files to prevent corruption
- The database files are located at: `astron/databases/astrondb/`
- After resetting, all accounts, toons, and game data will be deleted
- The database uses YAML files (`.yaml` or `.yml` extension) to store object data
