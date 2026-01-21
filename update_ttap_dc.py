#!/usr/bin/env python3
"""
Script to update imports and class names in ttap.dc file.
Handles file moves and class renames.
Automatically detects mappings from git status.
"""

import re
import subprocess
import sys
from pathlib import Path


def get_class_name_from_file(file_path, git_path=None):
    """Extract the class name from a Python file.
    
    Args:
        file_path: Path to the file (may not exist if moved)
        git_path: If file doesn't exist, try to get from git using this path
    """
    # Try reading from filesystem first
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    # Match: class ClassName( or class ClassName:
                    match = re.match(r'^\s*class\s+(\w+)', line)
                    if match:
                        return match.group(1)
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
    
    # If file doesn't exist, try to get from git
    if git_path:
        try:
            result = subprocess.run(
                ['git', 'show', f'HEAD:{git_path}'],
                capture_output=True,
                text=True,
                check=True
            )
            for line in result.stdout.split('\n'):
                match = re.match(r'^\s*class\s+(\w+)', line)
                if match:
                    return match.group(1)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    
    return None


def path_to_module_path(file_path_str):
    """Convert a file path to a module path (e.g., toontown/suit/file.py -> toontown.suit)."""
    # Use Path to get the parent directory, then convert to module path
    path = Path(file_path_str.replace('.py', ''))
    # Get parent directory (everything except the filename)
    parent = path.parent
    # Convert to string and replace path separators with dots
    module_path = str(parent).replace('/', '.').replace('\\', '.')
    # Handle case where parent is just '.' (current directory)
    if module_path == '.':
        return ''
    return module_path


def detect_mappings_from_git():
    """Detect file moves and class renames from git status."""
    mappings = []
    
    try:
        # Get git status with porcelain format
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError:
        print("Warning: Could not run git status. Falling back to manual mappings.")
        return []
    except FileNotFoundError:
        print("Warning: git not found. Falling back to manual mappings.")
        return []
    
    lines = result.stdout.strip().split('\n')
    if not lines or lines == ['']:
        return []
    
    repo_root = Path(__file__).parent
    
    for line in lines:
        # Parse git status lines like:
        # R  old/path/file.py -> new/path/file.py
        # RM old/path/file.py -> new/path/file.py
        if ' -> ' in line and (line.startswith('R ') or line.startswith('RM')):
            parts = line.split(' -> ')
            if len(parts) == 2:
                old_path_str = parts[0].split(maxsplit=1)[-1]  # Remove status prefix
                new_path_str = parts[1].strip()
                
                old_path = repo_root / old_path_str
                new_path = repo_root / new_path_str
                
                # Only process Python files that look like Distributed classes
                if old_path_str.endswith('.py') and 'Distributed' in old_path_str:
                    # Get class names from files
                    # Try to get old class from git if file doesn't exist
                    old_class = get_class_name_from_file(old_path, git_path=old_path_str)
                    new_class = get_class_name_from_file(new_path)
                    
                    # If still can't find, infer from filename
                    if old_class is None:
                        old_class = Path(old_path_str).stem
                    
                    if new_class is None:
                        new_class = Path(new_path_str).stem
                    
                    # Convert paths to module paths
                    old_module = path_to_module_path(old_path_str.rsplit('.py', 1)[0])
                    new_module = path_to_module_path(new_path_str.rsplit('.py', 1)[0])
                    
                    # Only add if class name or module changed
                    if old_class != new_class or old_module != new_module:
                        mappings.append((old_module, old_class, new_module, new_class))
                        print(f"Detected: {old_module}.{old_class} -> {new_module}.{new_class}")
    
    return mappings

def update_ttap_dc(file_path, mappings):
    """Update imports and class names in ttap.dc file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Update imports: from old_path import OldClass/AI -> from new_path import NewClass/AI
    for old_path, old_class, new_path, new_class in mappings:
        # Update import statements
        # Pattern: from old_path import OldClass/AI
        old_import = f"from {old_path} import {old_class}/AI"
        new_import = f"from {new_path} import {new_class}/AI"
        content = content.replace(old_import, new_import)
        
        # Update class definitions: dclass OldClass: -> dclass NewClass:
        # Match: dclass OldClass: or dclass OldClass (with optional whitespace)
        old_dclass = f"dclass {old_class}:"
        new_dclass = f"dclass {new_class}:"
        content = content.replace(old_dclass, new_dclass)
        
        # Also handle dclass with spaces: dclass OldClass : (with space before colon)
        old_dclass_spaced = f"dclass {old_class} :"
        new_dclass_spaced = f"dclass {new_class} :"
        content = content.replace(old_dclass_spaced, new_dclass_spaced)
    
    # Only write if changes were made
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {file_path}")
        return True
    else:
        print(f"No changes needed in {file_path}")
        return False

def main():
    script_dir = Path(__file__).parent
    ttap_dc_path = script_dir / "astron" / "dclass" / "ttap.dc"
    
    if not ttap_dc_path.exists():
        print(f"Error: {ttap_dc_path} not found")
        sys.exit(1)
    
    # Automatically detect mappings from git
    print("Detecting mappings from git status...")
    mappings = detect_mappings_from_git()
    
    if not mappings:
        print("No mappings detected. Nothing to update.")
        return
    
    print(f"\nFound {len(mappings)} mapping(s) to apply.\n")
    update_ttap_dc(ttap_dc_path, mappings)

if __name__ == "__main__":
    main()
