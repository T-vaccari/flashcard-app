import pandas as pd
import math
import uuid
import random
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FlashcardService:
    def __init__(self, file_path: str = "flashcards.csv"):
        self.file_path = file_path
        self.df = None
        self.study_queue = []  # List of indices
        self.session_stats = {"reviewed": 0, "total_due": 0}
        self.current_study_mode = None
        
        # Chapter names (Hardcoded as per original main.py)
        self.CHAPTER_NAMES = {
            1: "Fundamentals & SI Classification",
            2: "Enterprise Architecture & Process Modeling (ArchiMate + BPMN)",
            3: "Application Level (ERP, CRM)",
            4: "Data Analysis",
            5: "Platform Level (Integration: SOA, ESB, APIs)",
            6: "Physical Level (Infrastructure: Hardware, Servers, Cloud)",
            7: "Governance (Security + Strategy)",
        }

    def load_data(self) -> bool:
        """Loads data from CSV."""
        if not os.path.exists(self.file_path):
            logging.error(f"File not found: {self.file_path}")
            return False

        try:
            self.df = pd.read_csv(self.file_path, encoding='utf-8-sig')
            self._ensure_columns()
            self.df = self.df.fillna("") # Fill NaNs to avoid JSON issues
            # Ensure filtering out removed cards
            # But we keep them in DF, just filter later
            return True
        except Exception as e:
            logging.error(f"Error loading CSV: {e}")
            return False

    def _ensure_columns(self):
        """Ensures required columns exist."""
        required_columns = {
            'id': lambda: str(uuid.uuid4()),
            'front': '',
            'back': '',
            'last_review': '',
            'interval': 0,
            'ease_factor': 2.5,
            'repetitions': 0,
            'last_confidence': 0,
            'chapter': 1,
            'removed': 0
        }
        
        # Handle legacy column names if any
        column_mappings = {'domanda': 'front', 'risposta': 'back', 'question': 'front', 'answer': 'back'}
        for old, new in column_mappings.items():
            if old in self.df.columns and new not in self.df.columns:
                self.df[new] = self.df[old]

        for col, default in required_columns.items():
            if col not in self.df.columns:
                if callable(default):
                    self.df[col] = [default() for _ in range(len(self.df))]
                else:
                    self.df[col] = default
        
        # ID check
        if self.df['id'].isnull().any() or (self.df['id'] == '').any():
             # Basic way to fill missing IDs
             mask = self.df['id'].isnull() | (self.df['id'] == '')
             self.df.loc[mask, 'id'] = [str(uuid.uuid4()) for _ in range(mask.sum())]

    def save_data(self):
        """Saves DataFrame to CSV."""
        if self.df is not None:
            self.df.to_csv(self.file_path, index=False, encoding='utf-8-sig')

    def sm2_algorithm(self, card: dict, quality: int) -> dict:
        """Pure SM-2 implementation."""
        try:
            interval = int(float(card.get('interval', 0))) # Handle strings/floats safely
        except: interval = 0
            
        try:
            ease_factor = float(card.get('ease_factor', 2.5))
        except: ease_factor = 2.5
            
        try:
            repetitions = int(float(card.get('repetitions', 0)))
        except: repetitions = 0
        
        if quality < 3:
            repetitions = 0
            interval = 1
        else:
            if repetitions == 0:
                interval = 1
            elif repetitions == 1:
                interval = 6
            else:
                interval = math.ceil(interval * ease_factor)
            repetitions += 1
        
        ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        if ease_factor < 1.3:
            ease_factor = 1.3
            
        card['interval'] = interval
        card['ease_factor'] = round(ease_factor, 2)
        card['repetitions'] = repetitions
        # Use simple string for isoformat to be CSV friendly
        card['last_review'] = datetime.now().isoformat()
        card['last_confidence'] = quality
        
        return card

    def initialize_session(self, mode: str, chapters: Optional[List[int]] = None, confidence: Optional[int] = None):
        """Prepares the study queue based on filters."""
        if self.df is None: self.load_data()
        
        # Filter removed cards
        active_mask = (self.df['removed'] != 1)
        filtered_df = self.df[active_mask].copy()

        if mode == "due":
            filtered_df['last_review'] = filtered_df['last_review'].replace('', pd.NaT).replace('nan', pd.NaT)
            # Ensure we can parse dates
            filtered_df['last_review_dt'] = pd.to_datetime(filtered_df['last_review'], errors='coerce')
            
            def calc_due(row):
                if pd.isna(row['last_review_dt']): return datetime.min
                try:
                    return row['last_review_dt'] + timedelta(days=int(float(row['interval'])))
                except:
                    return datetime.min

            filtered_df['due_date'] = filtered_df.apply(calc_due, axis=1)
            today = datetime.now()
            
            # Apply chapter filter if present
            if chapters:
                filtered_df = filtered_df[filtered_df['chapter'].isin(chapters)]
                
            due_mask = filtered_df['due_date'] <= today
            self.study_queue = filtered_df[due_mask].sort_values(by='due_date').index.tolist()
            random.shuffle(self.study_queue)

        elif mode == "cram":
            # Just random shuffle of all matching criteria
            if chapters:
                filtered_df = filtered_df[filtered_df['chapter'].isin(chapters)]
            self.study_queue = filtered_df.index.tolist()
            random.shuffle(self.study_queue)
            
        elif mode == "confidence":
            if confidence is not None:
                filtered_df = filtered_df[filtered_df['last_confidence'] == confidence]
            self.study_queue = filtered_df.index.tolist()
            random.shuffle(self.study_queue)
            
        elif mode == "chapter":
             # Similar to cram but explicit naming
            if chapters:
                filtered_df = filtered_df[filtered_df['chapter'].isin(chapters)]
            self.study_queue = filtered_df.index.tolist()
            random.shuffle(self.study_queue)

        self.session_stats["total_due"] = len(self.study_queue)
        self.session_stats["reviewed"] = 0
        self.current_study_mode = mode
        
        return len(self.study_queue)

    def get_next_card(self) -> Optional[dict]:
        if not self.study_queue:
            return None
        # Get head of queue but don't pop yet (wait for review)
        idx = self.study_queue[0]
        card = self.df.loc[idx].to_dict()
        card['id'] = str(card['id']) # Ensure ID is string
        # Handle nan for Pydantic
        for k, v in card.items():
            if pd.isna(v): card[k] = ""
        return card

    def process_review(self, card_id: str, quality: int):
        # Find index in DF by ID (more robust than index matching if concurrent, though this is single user)
        # However, study_queue stores indices. Let's use the index from queue for O(1)
        if not self.study_queue: return False
        
        idx = self.study_queue[0]
        # Verify ID matches
        if str(self.df.at[idx, 'id']) != card_id:
            # Fallback search
            matches = self.df.index[self.df['id'] == card_id].tolist()
            if not matches: return False
            idx = matches[0]

        # Update Logic
        card_data = self.df.loc[idx].to_dict()
        updated = self.sm2_algorithm(card_data, quality)
        
        for k, v in updated.items():
            if k in self.df.columns:
                self.df.at[idx, k] = v
        
        self.save_data()
        
        # Pop from queue
        if idx in self.study_queue:
            self.study_queue.remove(idx) # Safe remove
            
        self.session_stats["reviewed"] += 1
        return True

    def get_stats(self):
        if self.df is None: self.load_data()
        
        total = len(self.df[self.df['removed'] != 1])
        
        # Calculate Due
        active_df = self.df[self.df['removed'] != 1].copy()
        active_df['last_review_dt'] = pd.to_datetime(active_df['last_review'], errors='coerce')
        # ... logic for due count ...
        # Simplified for stats:
        # Just check how many are due
        today = datetime.now()
        def is_due(row):
            if pd.isna(row['last_review_dt']): return True
            try: return row['last_review_dt'] + timedelta(days=int(float(row['interval']))) <= today
            except: return True
        
        due_count = active_df.apply(is_due, axis=1).sum()
        
        # Chapter breakdown
        chapters = active_df['chapter'].value_counts().to_dict()
        
        # Confidence breakdown
        confidence = active_df['last_confidence'].value_counts().to_dict()
        
        return {
            "total_cards": int(total),
            "due_cards": int(due_count),
            "chapters": {k: int(v) for k, v in chapters.items()},
            "confidence": {k: int(v) for k, v in confidence.items()}
        }

    def add_card(self, front: str, back: str, chapter: int):
        new_card = {
            'id': str(uuid.uuid4()),
            'front': front,
            'back': back,
            'chapter': chapter,
            'interval': 0, 'ease_factor': 2.5, 'repetitions': 0, 'removed': 0, 'last_review': '', 'last_confidence': 0
        }
        self.df = pd.concat([self.df, pd.DataFrame([new_card])], ignore_index=True)
        self.save_data()
        return new_card

    def update_card(self, card_id: str, updates: dict):
        matches = self.df.index[self.df['id'] == card_id].tolist()
        if not matches: return False
        idx = matches[0]
        
        for k, v in updates.items():
            if k in self.df.columns:
                self.df.at[idx, k] = v
        self.save_data()
        return True
    
    def delete_card(self, card_id: str):
        # Soft delete
        matches = self.df.index[self.df['id'] == card_id].tolist()
        if not matches: return False
        idx = matches[0]
        self.df.at[idx, 'removed'] = 1
        self.save_data()
        
        if idx in self.study_queue:
            self.study_queue.remove(idx)
            
        return True
