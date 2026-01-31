from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .services import FlashcardService
from .models import Card, ReviewRequest, StudyRequest, SessionStats
from typing import List, Dict
import os

app = FastAPI(title="Flashcard App API")

# CORS Setup
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serves frontend/dist
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(frontend_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_path, "assets")), name="assets")

# Singleton Service
service = FlashcardService()

@app.on_event("startup")
def startup_event():
    success = service.load_data()
    if not success:
        print("WARNING: Could not load data on startup.")

@app.get("/stats")
def get_stats():
    return service.get_stats()

@app.post("/study/start")
def start_study(request: StudyRequest):
    count = service.initialize_session(
        mode=request.mode, 
        chapters=request.chapters, 
        confidence=request.confidence_level
    )
    return {"count": count, "mode": request.mode}

@app.get("/study/next", response_model=Dict)
def get_next_card():
    card = service.get_next_card()
    # If no card, we might be done
    return {
        "card": card, 
        "finished": card is None,
        "stats": service.session_stats
    }

@app.post("/study/review/{card_id}")
def review_card(card_id: str, request: ReviewRequest):
    success = service.process_review(card_id, request.quality)
    if not success:
        raise HTTPException(status_code=404, detail="Card not found or not in queue")
    return {"success": True, "stats": service.session_stats}

@app.post("/cards")
def add_card(card: Card):
    # We ignore ID in input, generate new
    new_card = service.add_card(card.front, card.back, card.chapter)
    return new_card

@app.put("/cards/{card_id}")
def update_card(card_id: str, card: Card):
    updates = {
        "front": card.front,
        "back": card.back,
        "chapter": card.chapter,
        # Potentially other fields
    }
    success = service.update_card(card_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"success": True}

@app.delete("/cards/{card_id}")
def delete_card(card_id: str):
    success = service.delete_card(card_id)
    if not success:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"success": True}

@app.get("/chapters")
def get_chapters():
    return service.CHAPTER_NAMES

# SPA Catch-all (Must be last)
@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    if os.path.exists(frontend_path):
        file_path = os.path.join(frontend_path, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_path, "index.html"))
    return {"message": "Frontend not built. Run 'npm run build' in frontend/ directory."}
