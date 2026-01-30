# Flashcard SRS App

A flashcard study app using spaced repetition (SuperMemo-2 algorithm).

## Installation

**1. You need Python 3.10+**  
Get it from [python.org](https://www.python.org/downloads/)  
On Windows, check "Add Python to PATH" during installation.

**2. Clone the repo**
```bash
git clone https://github.com/tommasovaccari/flashcard-app.git
cd flashcard-app
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```
You can run the app in your browser:

```bash
flet run main.py --web
```

## Works on

- Windows
- macOS  
- Linux

## Troubleshooting

If `python` is not found, try `python3`.  

## 🏗️ Windows Setup (Detailed & Pyenv Users)

If you are on Windows, especially if using **pyenv-win**, follow these steps to avoid path/permission issues:

**1. Verify Python & Install**
Ensure you have a modern Python version (3.10+):
```powershell
python --version
```

**2. Create a Virtual Environment (Recommended)**
This enables a clean installation without admin rights or conflicting dependencies.
Open PowerShell/Terminal in the project folder:
```powershell
# Create the environment named 'venv'
python -m venv venv
```

**3. Activate the Environment**
You must do this every time you open a new terminal to work on the app.
```powershell
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
```
*Note: If you see a security error, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` first.*

**4. Install Dependencies**
With the environment activated (you should see `(venv)` in your prompt):
```powershell
pip install -r requirements.txt
```

**5. Run the App**
```powershell
flet run main.py
```

## 🌐 Web Version

You can run the app in your browser:

```bash
flet run main.py --web
```

---

*Built with [Claude Code](https://claude.ai)*
