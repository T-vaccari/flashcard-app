from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class Card(BaseModel):
    id: str
    front: str
    back: str
    chapter: int
    last_review: Optional[str] = None
    interval: int = 0
    ease_factor: float = 2.5
    repetitions: int = 0
    last_confidence: Optional[int] = None
    removed: int = 0

class ReviewRequest(BaseModel):
    quality: int

class StudyRequest(BaseModel):
    mode: str  # "due", "cram", "chapter", "confidence"
    chapters: Optional[List[int]] = None
    confidence_level: Optional[int] = None

class SessionStats(BaseModel):
    reviewed: int
    total_due: int
