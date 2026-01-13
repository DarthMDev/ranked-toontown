"""
This file is a hack to make the Nuitka build work.
In theory, we should be able to use the multidist mode, but results are mixed on Windows.
As we can't use multidist, we'd have to build the game 3 times (client, AI, UD).
So this file is a single entrypoint, so we only build once.
"""
import os
import sys

# Run dependency checker when launched directly (e.g., from PyCharm)
# Skip if SKIP_DEPENDENCY_CHECK is set (for developers who want to bypass)
# Skip if called from a launch script (they handle it themselves)
skip_check = os.environ.get("SKIP_DEPENDENCY_CHECK", "").lower() in ("1", "true", "yes")
called_from_script = os.environ.get("CALLED_FROM_LAUNCH_SCRIPT", "").lower() in ("1", "true", "yes")

if not skip_check and not called_from_script:
    try:
        # Try to import dependency_checker
        # Get the directory containing this file (launch/launcher/)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up two levels to get project root (launch/launcher -> launch -> root)
        project_root = os.path.dirname(os.path.dirname(current_dir))
        
        # Add project root to path if not already there
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        # Now try to import - use importlib for more reliable importing
        import importlib.util
        dependency_checker_path = os.path.join(current_dir, 'dependency_checker.py')
        if os.path.exists(dependency_checker_path):
            spec = importlib.util.spec_from_file_location("dependency_checker", dependency_checker_path)
            dependency_checker = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(dependency_checker)
        else:
            # Fallback to package import
            from launch.launcher import dependency_checker
        
        # Determine if MongoDB is required based on service type
        service_type = os.environ.get("SERVICE_TO_RUN", "")
        require_mongodb = service_type in ("AI", "UD")
        
        # For developers running from IDE, be less strict (warn instead of block)
        # For regular players, be strict (block if dependencies missing)
        is_developer_mode = os.environ.get("DEVELOPER_MODE", "").lower() in ("1", "true", "yes")
        
        if is_developer_mode:
            # Developer mode: quiet check, warn but don't block
            print("Developer mode: Running dependency check (non-blocking)...")
            dependency_checker.check_dependencies(require_mongodb=require_mongodb, quiet=True)
            # Note: check_dependencies returns False on failure, but we continue anyway in dev mode
            print("Note: Dependency check completed. Continuing in developer mode.")
        else:
            # Regular player mode: full check, block if dependencies are missing
            if not dependency_checker.check_dependencies(require_mongodb=require_mongodb, quiet=False):
                print("\nDependency check failed. Please install missing dependencies and try again.")
                print("To skip this check (developer mode), set SKIP_DEPENDENCY_CHECK=1 or DEVELOPER_MODE=1")
                sys.exit(1)
    except ImportError as e:
        # If dependency_checker can't be imported, warn but don't block
        print(f"Warning: Could not import dependency checker: {e}")
        print("Proceeding without dependency check...")
        print("Tip: Make sure you're running from the project root, or set SKIP_DEPENDENCY_CHECK=1")
    except Exception as e:
        # Don't block launch if dependency checker fails
        print(f"Warning: Dependency check encountered an error: {e}")
        print("Proceeding anyway...")

match os.environ.get("SERVICE_TO_RUN", None):
    case "CLIENT":
        from toontown.launcher import TTOffQuickStartLauncher
    case "AI":
        from toontown.ai import AIStart
    case "UD":
        from toontown.uberdog import UDStart
    case _:
        print("Unknown service type!")
