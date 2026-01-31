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

## 🌐 Web Version Guide

This project maintains two distinct versions on separate branches. Choose the one that fits your needs:

### 1. Main Branch (Flet - Python Only)
This is the lightweight version using Python and Flet.

**Steps:**
1. Switch to the main branch: `git checkout main`
2. Run the web server:
   ```bash
   flet run main.py --web
   ```
3. Open the provided URL (e.g., `http://127.0.0.1:8550`) in your browser.

**Note:** `flashcards.csv` is not tracked by git, so your study progress is local to your machine.

---

### 2. v2-web Branch (React + Python)
This version uses a React frontend for an enhanced web experience.

**Prerequisites:**
- **Node.js**: [Download here](https://nodejs.org/)
- **Python 3.10+**

**Steps:**
1. Switch to the web branch: `git checkout v2-web`
2. **Frontend Setup:**
   ```bash
   cd frontend
   npm install        # Install Node dependencies
   npm run dev        # Start the React development server
   ```
3. **Backend Setup:** (Open a new terminal)
   ```bash
   cd backend
   pip install -r requirements.txt
   python main.py
   ```
4. Access the app via the URL shown in the frontend terminal (usually `http://localhost:5173`).
---

*Built with [Claude Code](https://claude.ai)*
