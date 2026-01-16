#!/usr/bin/env python3
"""
Astron launcher script.
"""

import os
import sys
import subprocess
import tempfile
import atexit
import shutil

# Try to import PyYAML, and install it if missing
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    # Try to install PyYAML automatically
    try:
        import subprocess
        import sys
        print("PyYAML not found. Attempting to install...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyYAML"], 
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Try importing again
        import yaml
        YAML_AVAILABLE = True
        print("PyYAML installed successfully.")
    except Exception:
        # Installation failed, MongoDB is required
        pass

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

def create_mongodb_config(original_config_path):
    """Create a temporary config file with MongoDB backend."""
    if not YAML_AVAILABLE:
        print("ERROR: PyYAML not available. Cannot create MongoDB config.")
        sys.exit(1)
    
    try:
        # Read the original config
        with open(original_config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Modify the database backend to use MongoDB
        for role in config.get('roles', []):
            if role.get('type') == 'database':
                role['backend'] = {
                    'type': 'mongodb',
                    'server': 'mongodb://127.0.0.1:27017/astrondb'
                }
                break
        
        # Create a temporary config file
        config_dir = os.path.dirname(original_config_path)
        temp_path = os.path.join(config_dir, 'astrond_mongo_temp.yml')
        
        # Remove any existing temp file first
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        
        # Write the modified config
        with open(temp_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        print(f'Created temporary MongoDB config: {temp_path}')
        
        # Register cleanup function
        def cleanup():
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    print(f'Cleaned up temporary config: {temp_path}')
            except Exception:
                pass
        
        atexit.register(cleanup)
        return temp_path
    except Exception as e:
        print(f'ERROR: Failed to create MongoDB config: {e}')
        sys.exit(1)

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
    
    # Check if the default config already uses MongoDB
    # If it does, we don't need to create a temporary config
    config_uses_mongodb = False
    try:
        with open(config_path, 'r') as f:
            config_content = f.read()
            # Check if config already uses MongoDB backend
            if 'type: mongodb' in config_content or '"type": "mongodb"' in config_content:
                config_uses_mongodb = True
    except Exception as e:
        print(f'Warning: Could not read config file: {e}')
        print('Proceeding with default config...')
    
    if config_uses_mongodb:
        print('MongoDB detected and running. Using MongoDB backend from default config.')
        # Config already uses MongoDB, no need to modify
    else:
        # Config doesn't use MongoDB, need to create temp config
        if not YAML_AVAILABLE:
            print('ERROR: PyYAML is required to modify config but not available.')
            print('Please install PyYAML: pip install PyYAML')
            print('Or update astron/config/astrond.yml to use MongoDB backend manually.')
            sys.exit(1)
        print('MongoDB detected and running. Creating MongoDB config.')
        config_path = create_mongodb_config(config_path)
    
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
