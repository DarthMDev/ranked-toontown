#!/usr/bin/env python3
"""
Astron launcher script that verifies MongoDB is available before launching.
Since astrond.yml now uses MongoDB by default, we just need to verify MongoDB is running.
"""

import os
import sys
import subprocess

def check_mongodb_available():
    """Check if MongoDB is installed and running on the system."""
    try:
        from pymongo import MongoClient
        from pymongo.errors import ServerSelectionTimeoutError
        
        # Try to connect to MongoDB
        client = MongoClient('mongodb://127.0.0.1:27017/', serverSelectionTimeoutMS=2000)
        # Try to ping the server
        client.admin.command('ping')
        client.close()
        return True
    except (ImportError, ServerSelectionTimeoutError, Exception):
        # MongoDB is not available or not running
        return False

def main():
    # Get the project root (assuming this script is in launch/launcher/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    
    # Default config path
    default_config = os.path.join(project_root, 'astron', 'config', 'astrond.yml')
    
    # Check if config path is provided as argument
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        if not os.path.isabs(config_path):
            config_path = os.path.join(project_root, config_path)
    else:
        config_path = default_config
    
    # MongoDB is required - check if it's available
    if not check_mongodb_available():
        print('ERROR: MongoDB is required but not available.')
        print('Please install and start MongoDB before launching Astron.')
        print('MongoDB must be running on mongodb://127.0.0.1:27017/')
        sys.exit(1)
    
    # MongoDB is available - the default config already uses MongoDB
    print('MongoDB detected and running. Using MongoDB backend for Astron.')
    
    # Find astrond executable
    astron_dir = os.path.join(project_root, 'astron')
    
    # Determine executable name based on platform
    if sys.platform == 'win32':
        astrond_exe = os.path.join(astron_dir, 'astrond.exe')
    elif sys.platform == 'darwin':
        astrond_exe = os.path.join(astron_dir, 'astrondmac')
    else:
        astrond_exe = os.path.join(astron_dir, 'astrondlinux')
    
    if not os.path.exists(astrond_exe):
        print(f'Error: Astron executable not found at {astrond_exe}')
        sys.exit(1)
    
    # Change to astron directory
    os.chdir(astron_dir)
    
    # Get relative config path from astron directory
    if os.path.isabs(config_path):
        config_relative = os.path.relpath(config_path, astron_dir)
    else:
        config_relative = config_path
    
    # Build command
    cmd = [astrond_exe, '--loglevel', 'info', config_relative]
    
    # Add any additional arguments
    if len(sys.argv) > 2:
        cmd.extend(sys.argv[2:])
    
    print(f'Starting Astron with config: {config_relative}')
    print(f'Command: {" ".join(cmd)}')
    print()
    print('NOTE: If you see "address already in use" error, another Astron instance is already running.')
    print('Please stop the existing instance before starting a new one.')
    print()
    
    # Launch Astron
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print('\nAstron stopped by user.')
    except Exception as e:
        print(f'Error launching Astron: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()
