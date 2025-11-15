#!/usr/bin/env python
"""
Setup script for Sentinel AI Launcher

This script helps install dependencies for both frontend and backend.

WARNING: This will install 294 backend + 11 frontend packages (~4GB download).
Expected time: 20-60 minutes depending on internet speed.

For faster installation, see INSTALL.md
"""

import subprocess
import sys
from pathlib import Path
import time


def run_command(command, cwd=None, show_output=True):
    """Run a shell command and return success status."""
    try:
        print(f"\nRunning: {command}")
        if show_output:
            print("\n" + "="*60)
            print("LIVE OUTPUT (this may take 15-30 minutes):")
            print("="*60)
            # Stream output in real-time so user sees progress
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in process.stdout:
                print(line, end='')

            process.wait()

            if process.returncode != 0:
                print(f"\nError: Command failed with exit code {process.returncode}")
                return False

            return True
        else:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True
            )
            print(result.stdout)
            return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        if hasattr(e, 'stderr'):
            print(e.stderr)
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def install_dependencies():
    """Install dependencies for both frontend and backend."""
    project_root = Path(__file__).parent

    print("="*60)
    print("Sentinel AI - Dependency Installation")
    print("="*60)
    print("\n⚠ WARNING: This will install ~305 packages (~4GB)")
    print("⏱ Expected time: 20-60 minutes")
    print("\nPress Ctrl+C to cancel, or press Enter to continue...")
    try:
        input()
    except KeyboardInterrupt:
        print("\nInstallation cancelled.")
        return False

    start_time = time.time()

    # Install backend dependencies
    backend_path = project_root / "Sentinel-AI-Backend"
    if backend_path.exists():
        print("\n[1/2] Installing Backend Dependencies (294 packages)...")
        print("This is the slow part - PyTorch, Transformers, LangChain, etc.")
        print("Expected: 15-30 minutes\n")
        backend_requirements = backend_path / "requirements.txt"
        if backend_requirements.exists():
            backend_start = time.time()
            success = run_command(
                f'"{sys.executable}" -m pip install -r "{backend_requirements}" --progress-bar on',
                show_output=True
            )
            backend_time = time.time() - backend_start
            if success:
                print(f"✓ Backend dependencies installed in {backend_time/60:.1f} minutes")
            else:
                print("✗ Failed to install backend dependencies")
                return False
        else:
            print("Warning: Backend requirements.txt not found")
    else:
        print("Error: Sentinel-AI-Backend directory not found")
        return False

    # Install frontend dependencies
    frontend_path = project_root / "Sentinel-AI-Frontend"
    if frontend_path.exists():
        print("\n[2/2] Installing Frontend Dependencies (11 packages)...")
        print("This should be quick - PyQt5 and MongoDB drivers")
        print("Expected: 2-5 minutes\n")
        frontend_requirements = frontend_path / "requirements.txt"
        if frontend_requirements.exists():
            frontend_start = time.time()
            success = run_command(
                f'"{sys.executable}" -m pip install -r "{frontend_requirements}" --progress-bar on',
                show_output=True
            )
            frontend_time = time.time() - frontend_start
            if success:
                print(f"✓ Frontend dependencies installed in {frontend_time/60:.1f} minutes")
            else:
                print("✗ Failed to install frontend dependencies")
                return False
        else:
            print("Warning: Frontend requirements.txt not found")
    else:
        print("Error: Sentinel-AI-Frontend directory not found")
        return False

    total_time = time.time() - start_time
    print("\n" + "="*60)
    print("Installation Complete!")
    print("="*60)
    print(f"\n⏱ Total time: {total_time/60:.1f} minutes")
    print("\nNext steps:")
    print("1. Configure .env files in both Sentinel-AI-Backend and Sentinel-AI-Frontend")
    print("2. Run: python launcher.py")
    print("="*60)

    return True


def check_environment():
    """Check if the environment is properly configured."""
    project_root = Path(__file__).parent

    print("\n" + "="*60)
    print("Environment Check")
    print("="*60)

    issues = []

    # Check backend .env
    backend_env = project_root / "Sentinel-AI-Backend" / ".env"
    if not backend_env.exists():
        issues.append("Backend .env file is missing")
    else:
        print("✓ Backend .env file found")

    # Check frontend .env
    frontend_env = project_root / "Sentinel-AI-Frontend" / ".env"
    if not frontend_env.exists():
        issues.append("Frontend .env file is missing")
    else:
        print("✓ Frontend .env file found")

    # Check Google credentials for frontend
    credentials = project_root / "Sentinel-AI-Frontend" / "credentials.json"
    if not credentials.exists():
        issues.append("Frontend credentials.json is missing (required for Google Meet integration)")
    else:
        print("✓ Frontend credentials.json found")

    if issues:
        print("\n⚠ Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nPlease resolve these issues before running the launcher.")
        return False
    else:
        print("\n✓ All configuration files found!")
        return True


def check_if_installed():
    """Check if dependencies are already installed."""
    print("\n" + "="*60)
    print("Checking if dependencies are already installed...")
    print("="*60)

    backend_ok = False
    frontend_ok = False

    # Check backend
    try:
        sys.path.insert(0, str(Path(__file__).parent / "Sentinel-AI-Backend"))
        import langchain
        import langgraph
        print("✓ Backend dependencies appear to be installed")
        backend_ok = True
    except ImportError as e:
        print(f"✗ Backend dependencies missing: {e.name}")

    # Check frontend
    try:
        sys.path.insert(0, str(Path(__file__).parent / "Sentinel-AI-Frontend"))
        from PyQt5.QtWidgets import QApplication
        import pymongo
        print("✓ Frontend dependencies appear to be installed")
        frontend_ok = True
    except ImportError as e:
        print(f"✗ Frontend dependencies missing: {e.name}")

    if backend_ok and frontend_ok:
        print("\n" + "="*60)
        print("✓ All dependencies already installed!")
        print("="*60)
        print("\nYou can skip installation and run directly:")
        print("  python launcher.py")
        print("\nOr reinstall anyway if having issues.")
        return True

    return False


def main():
    """Main setup function."""
    print("="*60)
    print("Sentinel AI Launcher Setup")
    print("="*60)
    print()

    # Check directory structure
    project_root = Path(__file__).parent
    if not (project_root / "Sentinel-AI-Backend").exists():
        print("Error: Sentinel-AI-Backend directory not found")
        sys.exit(1)
    if not (project_root / "Sentinel-AI-Frontend").exists():
        print("Error: Sentinel-AI-Frontend directory not found")
        sys.exit(1)

    # Check if already installed
    already_installed = check_if_installed()

    # Ask user what to do
    print("\nWhat would you like to do?")
    print("1. Install dependencies (20-60 min, ~4GB download)")
    print("2. Check environment configuration")
    print("3. Both (install + check)")
    if already_installed:
        print("4. Skip to running launcher (recommended)")
    print()

    choice = input("Enter choice (1-4): ").strip()

    if choice == "1":
        install_dependencies()
    elif choice == "2":
        check_environment()
    elif choice == "3":
        if install_dependencies():
            check_environment()
    elif choice == "4" and already_installed:
        print("\nGreat! Run this command:")
        print("  python launcher.py")
    else:
        print("Invalid choice")
        sys.exit(1)


if __name__ == "__main__":
    main()
