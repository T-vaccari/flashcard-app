import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

def main():
    print("Starting Flashcard App...")
    
    # Check if .venv exists
    venv_path = Path(".venv")
    if sys.platform == "win32":
        python_executable = venv_path / "Scripts" / "python.exe"
    else:
        python_executable = venv_path / "bin" / "python"

    if not python_executable.exists():
        print(f"Virtual environment not found at {python_executable}.")
        print("Attempting to use system python...")
        python_executable = sys.executable

    # Command to run uvicorn
    # We run it as a module to ensure imports work
    cmd = [str(python_executable), "-m", "uvicorn", "backend.main:app", "--port", "8000", "--host", "127.0.0.1"]
    
    print(f"Running backend: {' '.join(cmd)}")
    try:
        # Start backend in subprocess
        process = subprocess.Popen(cmd)
        
        # Wait a moment for server to start
        time.sleep(2)
        
        print("Opening browser...")
        webbrowser.open("http://127.0.0.1:8000")
        
        print("App is running. Press Ctrl+C to stop.")
        process.wait()
    except KeyboardInterrupt:
        print("\nStopping...")
        process.terminate()
    except Exception as e:
        print(f"Error: {e}")
        if 'process' in locals():
            process.terminate()

if __name__ == "__main__":
    main()
