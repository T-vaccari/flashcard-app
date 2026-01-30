import flet as ft
import pandas as pd
import pathlib
import math
import uuid
import random
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- SM-2 Algorithm (Pure Function) ---

def calculate_next_review(card: dict, quality: int) -> dict:
    """
    Implements the SuperMemo-2 (SM-2) algorithm.
    
    Args:
        card (dict): A dictionary representing the flashcard with keys:
                     'interval', 'ease_factor', 'repetitions'.
        quality (int): The user's rating of the review quality (0-5).
        
    Returns:
        dict: The updated card dictionary.
    """
    # Extract current values with defaults
    try:
        interval = int(card.get('interval', 0))
    except (ValueError, TypeError):
        interval = 0
        
    try:
        ease_factor = float(card.get('ease_factor', 2.5))
    except (ValueError, TypeError):
        ease_factor = 2.5
        
    try:
        repetitions = int(card.get('repetitions', 0))
    except (ValueError, TypeError):
        repetitions = 0
    
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
    
    # Update Ease Factor
    # EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if ease_factor < 1.3:
        ease_factor = 1.3
        
    # Update card dictionary
    card['interval'] = interval
    card['ease_factor'] = round(ease_factor, 2)
    card['repetitions'] = repetitions
    card['last_review'] = datetime.now().isoformat()
    
    return card

# --- State Management ---

# Chapter names mapping (7-chapter layered structure)
CHAPTER_NAMES = {
    1: "Fundamentals & SI Classification",
    2: "Enterprise Architecture & Process Modeling (ArchiMate + BPMN)",
    3: "Application Level (ERP, CRM)",
    4: "Data Analysis",
    5: "Platform Level (Integration: SOA, ESB, APIs)",
    6: "Physical Level (Infrastructure: Hardware, Servers, Cloud)",
    7: "Governance (Security + Strategy)",
}

class FlashcardApp:
    def __init__(self):
        self.df = None
        self.current_file_path = None
        self.study_queue = [] # List of indices in self.df
        self.current_card_index = None # Index in self.df
        self.queue_position = 0  # Current position in study queue
        self.current_study_mode = None  # 'random', 'confidence', or 'chapter'
        self.session_stats = {"reviewed": 0, "total_due": 0}

    def load_data(self, file_path: str):
        """
        Loads data from CSV, ensures schema, and sorts by priority.
        """
        try:
            path = pathlib.Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            # Read CSV with utf-8-sig
            self.df = pd.read_csv(path, encoding='utf-8-sig')
            self.current_file_path = path

            # Support multiple column naming conventions
            # Map 'domanda'/'risposta' to 'front'/'back' if needed
            column_mappings = {
                'domanda': 'front',
                'risposta': 'back',
                'question': 'front',
                'answer': 'back'
            }
            for old_name, new_name in column_mappings.items():
                if old_name in self.df.columns and new_name not in self.df.columns:
                    self.df[new_name] = self.df[old_name]
                elif old_name in self.df.columns and new_name in self.df.columns:
                    # If 'front'/'back' exist but are empty, fill from 'domanda'/'risposta'
                    mask = self.df[new_name].isna() | (self.df[new_name] == '')
                    self.df.loc[mask, new_name] = self.df.loc[mask, old_name]

            # Ensure required columns exist
            required_columns = {
                'id': lambda: str(uuid.uuid4()),
                'front': '',
                'back': '',
                'last_review': '', # NaT or empty string
                'interval': 0,
                'ease_factor': 2.5,
                'repetitions': 0,
                'last_confidence': 0,  # Stores user's last confidence rating (1-5)
                'removed': 0  # Flag to hide cards (1 = removed)
            }

            for col, default in required_columns.items():
                if col not in self.df.columns:
                    if callable(default):
                        self.df[col] = [default() for _ in range(len(self.df))]
                    else:
                        self.df[col] = default

            # Fill NaNs for critical logic columns
            self.df['interval'] = self.df['interval'].fillna(0).astype(int)
            self.df['ease_factor'] = self.df['ease_factor'].fillna(2.5).astype(float)
            self.df['repetitions'] = self.df['repetitions'].fillna(0).astype(int)
            self.df['last_review'] = self.df['last_review'].fillna('')
            self.df['last_confidence'] = self.df['last_confidence'].fillna(0).astype(int)
            self.df['removed'] = self.df['removed'].fillna(0).astype(int)
            
            # Filter out removed cards for all operations
            active_mask = self.df['removed'] != 1
            
            # Fill NaN values in front/back with empty string
            self.df['front'] = self.df['front'].fillna('')
            self.df['back'] = self.df['back'].fillna('')

            # Generate IDs if missing
            if self.df['id'].isnull().any():
                 self.df.loc[self.df['id'].isnull(), 'id'] = [str(uuid.uuid4()) for _ in range(self.df['id'].isnull().sum())]

            # --- Sorting Logic (Priority Queue) ---
            # 1. Convert last_review to datetime
            # Handle empty strings or invalid formats gracefully by coercing to NaT
            temp_last_review = pd.to_datetime(self.df['last_review'], errors='coerce')
            
            # 2. Calculate due_date
            # due_date = last_review + timedelta(days=interval)
            # We use a lambda to handle NaT safely
            def calculate_due_date(row):
                if pd.isna(row['last_review_dt']):
                    return datetime.min # Treat never reviewed as very old (high priority)
                return row['last_review_dt'] + timedelta(days=row['interval'])

            # Create a temporary dataframe for sorting to avoid messing up the original index yet
            sort_df = self.df.copy()
            sort_df['last_review_dt'] = temp_last_review
            sort_df['due_date'] = sort_df.apply(calculate_due_date, axis=1)
            
            # 3. Filter: due_date <= today OR last_review is Null (handled by datetime.min above)
            #    AND card is not removed
            today = datetime.now()
            # We want cards where due_date is in the past or today AND not removed
            due_mask = (sort_df['due_date'] <= today) & (active_mask)
            
            # Get indices of due cards, sorted by due_date ascending
            due_cards = sort_df[due_mask].sort_values(by='due_date', ascending=True)
            
            self.study_queue = due_cards.index.tolist()
            # Shuffle cards randomly for varied study order
            random.shuffle(self.study_queue)
            self.session_stats["total_due"] = len(self.study_queue)
            self.session_stats["reviewed"] = 0
            self.queue_position = 0
            self.current_study_mode = "random"
            
            logging.info(f"Loaded {len(self.df)} cards. {len(self.study_queue)} due for review (shuffled).")
            
            # Save immediately to ensure schema consistency
            self.save_data()
            
            return True, f"Loaded {len(self.study_queue)} cards due."

        except Exception as e:
            logging.error(f"Error loading file: {e}")
            return False, str(e)

    def save_data(self):
        """Saves the current DataFrame to CSV."""
        if self.df is not None and self.current_file_path:
            self.df.to_csv(self.current_file_path, index=False, encoding='utf-8-sig')

    def get_next_card(self):
        """Retrieves the card at current queue position."""
        if not self.study_queue or self.queue_position >= len(self.study_queue):
            return None
        
        self.current_card_index = self.study_queue[self.queue_position]
        # Return as a dictionary
        return self.df.loc[self.current_card_index].to_dict()

    def navigate_card(self, direction: int):
        """
        Navigate to previous/next card without reviewing.
        
        Args:
            direction: -1 for previous, +1 for next
        
        Returns:
            dict or None: The new card, or None if at boundary
        """
        new_position = self.queue_position + direction
        if 0 <= new_position < len(self.study_queue):
            self.queue_position = new_position
            return self.get_next_card()
        return None

    def update_card_chapter(self, new_chapter: int):
        """
        Update the chapter of the current card.
        
        Args:
            new_chapter: New chapter number (1-9)
        """
        if self.current_card_index is not None and self.df is not None:
            self.df.at[self.current_card_index, 'chapter'] = new_chapter
            self.save_data()
            return True
        return False

    def remove_current_card(self):
        """
        Mark the current card as removed (won't appear in future sessions).
        
        Returns:
            bool: True if card was removed, False otherwise
        """
        if self.current_card_index is not None and self.df is not None:
            self.df.at[self.current_card_index, 'removed'] = 1
            self.save_data()
            
            # Remove from current queue
            if self.queue_position < len(self.study_queue):
                self.study_queue.pop(self.queue_position)
                if self.queue_position >= len(self.study_queue):
                    self.queue_position = max(0, len(self.study_queue) - 1)
            
            self.current_card_index = None
            return True
        return False

    def update_card_answer(self, new_answer: str) -> bool:
        """
        Update the answer of the current card.
        
        Args:
            new_answer: The new answer text
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self.current_card_index is None or self.df is None:
            return False
        
        self.df.at[self.current_card_index, 'back'] = new_answer
        self.df.at[self.current_card_index, 'risposta'] = new_answer
        self.save_data()
        return True

    def add_new_flashcard(self, question: str, answer: str, chapter: int = 1) -> bool:
        """
        Add a new flashcard to the database.
        
        Args:
            question: The question text
            answer: The answer text  
            chapter: Chapter number (1-9)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self.df is None:
            return False
        
        new_card = {
            'domanda': question,
            'risposta': answer,
            'id': str(uuid.uuid4()),
            'front': question,
            'back': answer,
            'last_review': '',
            'interval': 0,
            'ease_factor': 2.5,
            'repetitions': 0,
            'last_confidence': 0,
            'chapter': chapter,
            'removed': 0
        }
        
        self.df = pd.concat([self.df, pd.DataFrame([new_card])], ignore_index=True)
        self.save_data()
        return True

    def process_review(self, quality: int):
        """Updates the current card based on review quality."""
        if self.current_card_index is None:
            return

        # Get current card data
        card_data = self.df.loc[self.current_card_index].to_dict()
        
        # Calculate new state
        updated_card = calculate_next_review(card_data, quality)
        
        # Update DataFrame
        for key, value in updated_card.items():
            if key in self.df.columns:
                self.df.at[self.current_card_index, key] = value
        
        # Save confidence rating
        self.df.at[self.current_card_index, 'last_confidence'] = quality
        
        # Save to disk
        self.save_data()
        
        # Remove current card from queue and adjust position
        self.study_queue.pop(self.queue_position)
        self.session_stats["reviewed"] += 1
        # Don't advance position since we removed the current item
        # But ensure we don't go past the end
        if self.queue_position >= len(self.study_queue):
            self.queue_position = max(0, len(self.study_queue) - 1)
        self.current_card_index = None

    def get_confidence_counts(self):
        """Returns count of active (non-removed) cards for each confidence level (0-5)."""
        if self.df is None:
            return {i: 0 for i in range(6)}
        
        active_df = self.df[self.df['removed'] != 1]
        counts = active_df['last_confidence'].value_counts().to_dict()
        return {i: counts.get(i, 0) for i in range(6)}

    def load_by_confidence(self, file_path: str, confidence_level: int):
        """
        Load cards filtered by a specific confidence level.
        
        Args:
            file_path: Path to CSV file
            confidence_level: Confidence level to filter (0-5)
        """
        # First load all data normally
        success, message = self.load_data(file_path)
        if not success:
            return False, message
        
        # Filter study queue to only cards with matching confidence (excluding removed)
        filtered_indices = self.df[
            (self.df['last_confidence'] == confidence_level) & (self.df['removed'] != 1)
        ].index.tolist()
        
        # Shuffle filtered cards
        random.shuffle(filtered_indices)
        
        self.study_queue = filtered_indices
        self.session_stats["total_due"] = len(self.study_queue)
        self.session_stats["reviewed"] = 0
        self.queue_position = 0
        self.current_study_mode = "confidence"
        
        logging.info(f"Filtered to {len(self.study_queue)} cards with confidence {confidence_level}")
        
        return True, f"Loaded {len(self.study_queue)} cards with confidence {confidence_level}"

    def get_chapter_counts(self):
        """Returns count of active (non-removed) cards for each chapter."""
        if self.df is None or 'chapter' not in self.df.columns:
            return {i: 0 for i in range(1, 8)}
        
        active_df = self.df[self.df['removed'] != 1]
        counts = active_df['chapter'].value_counts().to_dict()
        return {i: counts.get(i, 0) for i in range(1, 8)}

    def load_by_chapters(self, file_path: str, selected_chapters: list):
        """
        Load cards filtered by selected chapters.
        
        Args:
            file_path: Path to CSV file
            selected_chapters: List of chapter numbers to include
        """
        # First load all data normally
        success, message = self.load_data(file_path)
        if not success:
            return False, message
        
        if 'chapter' not in self.df.columns:
            return False, "No 'chapter' column found in CSV"
        
        # Filter study queue to only cards with matching chapters (excluding removed)
        filtered_indices = self.df[
            (self.df['chapter'].isin(selected_chapters)) & (self.df['removed'] != 1)
        ].index.tolist()
        
        # Shuffle filtered cards
        random.shuffle(filtered_indices)
        
        self.study_queue = filtered_indices
        self.session_stats["total_due"] = len(self.study_queue)
        self.session_stats["reviewed"] = 0
        self.queue_position = 0
        self.current_study_mode = "chapter"
        
        chapter_names = [CHAPTER_NAMES.get(c, f"Ch.{c}") for c in selected_chapters]
        logging.info(f"Filtered to {len(self.study_queue)} cards from chapters: {selected_chapters}")
        
        return True, f"Loaded {len(self.study_queue)} cards from {len(selected_chapters)} chapter(s)"


# --- UI Construction ---

def main(page: ft.Page):
    page.title = "Flashcard SRS App"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    
    # Custom light theme with modern colors
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary="#6366f1",
            secondary="#8b5cf6",
            surface=ft.Colors.WHITE,
            background=ft.Colors.GREY_50,
        )
    )
    
    # Initialize App State
    app_state = FlashcardApp()
    
    # --- Views ---
    
    def get_home_view():
        DEFAULT_PATH = "flashcards.csv"
        
        # Auto-load data on home view to get counts
        if pathlib.Path(DEFAULT_PATH).exists() and app_state.df is None:
            app_state.load_data(DEFAULT_PATH)
        
        def start_random_study(e):
            if pathlib.Path(DEFAULT_PATH).exists():
                success, message = app_state.load_data(DEFAULT_PATH)
                if success:
                    if app_state.study_queue:
                        page.go("/study")
                    else:
                        page.snack_bar = ft.SnackBar(ft.Text("All cards have been studied! Come back later."), bgcolor=ft.Colors.AMBER)
                        page.snack_bar.open = True
                        page.update()
                else:
                    page.snack_bar = ft.SnackBar(ft.Text(f"Error: {message}"), bgcolor=ft.Colors.ERROR)
                    page.snack_bar.open = True
                    page.update()
            else:
                page.snack_bar = ft.SnackBar(ft.Text("flashcards.csv not found!"), bgcolor=ft.Colors.ERROR)
                page.snack_bar.open = True
                page.update()


        # ===== ADD FLASHCARD DIALOG =====
        def open_add_flashcard_dialog(e):
            question_field = ft.TextField(
                label="Domanda",
                multiline=True,
                min_lines=2,
                max_lines=5,
                width=500
            )
            answer_field = ft.TextField(
                label="Risposta",
                multiline=True,
                min_lines=3,
                max_lines=10,
                width=500
            )
            chapter_dropdown = ft.Dropdown(
                label="Capitolo",
                value="1",
                options=[
                    ft.dropdown.Option(str(i), f"Ch. {i}: {CHAPTER_NAMES.get(i, '')}")
                    for i in range(1, 8)
                ],
                width=500
            )
            
            def save_new_card(e):
                if not question_field.value or not answer_field.value:
                    page.snack_bar = ft.SnackBar(
                        ft.Text("⚠️ Compila domanda e risposta!"),
                        bgcolor=ft.Colors.ORANGE
                    )
                    page.snack_bar.open = True
                    page.update()
                    return
                
                if app_state.add_new_flashcard(
                    question_field.value,
                    answer_field.value,
                    int(chapter_dropdown.value)
                ):
                    page.close(dlg)
                    page.snack_bar = ft.SnackBar(
                        ft.Text("✅ Flashcard aggiunta!"),
                        bgcolor=ft.Colors.GREEN_600
                    )
                    page.snack_bar.open = True
                    # Refresh home view to update counts
                    page.views.pop()
                    page.views.append(get_home_view())
                    page.update()
            
            dlg = ft.AlertDialog(
                title=ft.Text("Aggiungi Nuova Flashcard"),
                content=ft.Column([
                    question_field,
                    answer_field,
                    chapter_dropdown
                ], tight=True, spacing=15),
                actions=[
                    ft.TextButton("Annulla", on_click=lambda e: page.close(dlg)),
                    ft.ElevatedButton("Aggiungi", on_click=save_new_card),
                ]
            )
            page.open(dlg)

        # ===== CONFIDENCE SECTION =====
        confidence_colors = {
            1: ft.Colors.RED_400,
            2: ft.Colors.ORANGE_400,
            3: ft.Colors.YELLOW_600,
            4: ft.Colors.LIGHT_GREEN_400,
            5: ft.Colors.GREEN_400,
        }
        
        confidence_labels = {
            1: "😟 Hard",
            2: "😕 Difficult", 
            3: "😐 So-so",
            4: "🙂 Good",
            5: "😊 Easy",
        }
        
        def load_by_confidence_click(confidence_level):
            def handler(e):
                success, message = app_state.load_by_confidence(DEFAULT_PATH, confidence_level)
                if success:
                    if app_state.study_queue:
                        page.go("/study")
                    else:
                        page.snack_bar = ft.SnackBar(ft.Text(f"No cards with confidence {confidence_level}"), bgcolor=ft.Colors.AMBER)
                        page.snack_bar.open = True
                        page.update()
                else:
                    page.snack_bar = ft.SnackBar(ft.Text(f"Error: {message}"), bgcolor=ft.Colors.ERROR)
                    page.snack_bar.open = True
                    page.update()
            return handler
        
        confidence_counts = app_state.get_confidence_counts()
        
        confidence_buttons = ft.Row(
            [
                ft.ElevatedButton(
                    f"{confidence_labels[i]} ({confidence_counts.get(i, 0)})",
                    bgcolor=confidence_colors[i],
                    color=ft.Colors.WHITE,
                    on_click=load_by_confidence_click(i),
                    style=ft.ButtonStyle(padding=10)
                )
                for i in range(1, 6)
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            wrap=True,
            spacing=10
        )

        # ===== CHAPTER SELECTION SECTION =====
        chapter_counts = app_state.get_chapter_counts()
        selected_chapters = {i: False for i in range(1, 8)}
        chapter_checkboxes = []
        
        def on_chapter_toggle(chapter_num):
            def handler(e):
                selected_chapters[chapter_num] = e.control.value
                # Update start button state
                any_selected = any(selected_chapters.values())
                start_chapters_btn.disabled = not any_selected
                page.update()
            return handler
        
        def select_all_chapters(e):
            for i, cb in enumerate(chapter_checkboxes, 1):
                cb.value = True
                selected_chapters[i] = True
            start_chapters_btn.disabled = False
            page.update()
        
        def deselect_all_chapters(e):
            for i, cb in enumerate(chapter_checkboxes, 1):
                cb.value = False
                selected_chapters[i] = False
            start_chapters_btn.disabled = True
            page.update()
        
        def start_chapter_study(e):
            chapters_to_study = [ch for ch, selected in selected_chapters.items() if selected]
            if not chapters_to_study:
                page.snack_bar = ft.SnackBar(ft.Text("Select at least one chapter!"), bgcolor=ft.Colors.ERROR)
                page.snack_bar.open = True
                page.update()
                return
            
            success, message = app_state.load_by_chapters(DEFAULT_PATH, chapters_to_study)
            if success:
                if app_state.study_queue:
                    page.go("/study")
                else:
                    page.snack_bar = ft.SnackBar(ft.Text("No cards in selected chapters"), bgcolor=ft.Colors.AMBER)
                    page.snack_bar.open = True
                    page.update()
            else:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {message}"), bgcolor=ft.Colors.ERROR)
                page.snack_bar.open = True
                page.update()
        
        # Create chapter checkboxes
        for i in range(1, 8):
            count = chapter_counts.get(i, 0)
            cb = ft.Checkbox(
                label=f"Ch. {i}: {CHAPTER_NAMES.get(i, '')} ({count})",
                value=False,
                on_change=on_chapter_toggle(i)
            )
            chapter_checkboxes.append(cb)
        
        start_chapters_btn = ft.ElevatedButton(
            "📚 Study Selected Chapters",
            icon=ft.Icons.PLAY_ARROW,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PURPLE_400,
                color=ft.Colors.WHITE,
                padding=15
            ),
            disabled=True,
            on_click=start_chapter_study
        )
        
        chapter_section = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.TextButton("Select all", on_click=select_all_chapters),
                            ft.TextButton("Deselect all", on_click=deselect_all_chapters),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=20
                    ),
                    ft.Container(
                        content=ft.Column(
                            chapter_checkboxes,
                            spacing=5,
                            scroll=ft.ScrollMode.AUTO
                        ),
                        height=220,
                        border=ft.border.all(1, "#e5e7eb"),
                        border_radius=10,
                        padding=15
                    ),
                    ft.Container(height=10),
                    start_chapters_btn
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10
            ),
        )

        # ===== MAIN VIEW =====
        total_cards = len(app_state.df) if app_state.df is not None else 0
        due_cards = len(app_state.study_queue) if app_state.study_queue else 0
        
        return ft.View(
            "/",
            [
                ft.Container(
                    content=ft.Column(
                        [
                            # Header
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Icon(ft.Icons.AUTO_STORIES, size=64, color="#6366f1"),
                                        ft.Text(
                                            "Flashcard SRS", 
                                            size=32, 
                                            weight=ft.FontWeight.BOLD,
                                            color="#1f2937"
                                        ),
                                        ft.Text(
                                            "SuperMemo-2 Spaced Repetition", 
                                            size=14, 
                                            color="#6b7280",
                                            italic=True
                                        ),
                                        ft.Container(height=8),
                                        ft.Container(
                                            content=ft.Text(
                                                f"📚 {total_cards} cards  •  ⏰ {due_cards} due for review", 
                                                size=13, 
                                                color="#374151"
                                            ),
                                            bgcolor="#f3f4f6",
                                            padding=ft.padding.symmetric(horizontal=16, vertical=8),
                                            border_radius=20,
                                        ),
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=4,
                                ),
                                padding=ft.padding.only(top=20, bottom=20),
                            ),
                            
                            # Main Actions Card
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.ElevatedButton(
                                            "🎲 Random Study",
                                            icon=ft.Icons.SHUFFLE,
                                            on_click=start_random_study,
                                            style=ft.ButtonStyle(
                                                bgcolor="#6366f1",
                                                color="#ffffff",
                                                padding=18,
                                                shape=ft.RoundedRectangleBorder(radius=10),
                                            ),
                                            expand=True,
                                            height=50,
                                        ),
                                        ft.OutlinedButton(
                                            "➕ Add Flashcard",
                                            icon=ft.Icons.ADD_CARD,
                                            on_click=open_add_flashcard_dialog,
                                            style=ft.ButtonStyle(
                                                color="#10b981",
                                                padding=14,
                                                shape=ft.RoundedRectangleBorder(radius=10),
                                                side=ft.BorderSide(1.5, "#10b981"),
                                            ),
                                            expand=True,
                                            height=46,
                                        ),
                                    ],
                                    spacing=10,
                                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                ),
                                bgcolor=ft.Colors.WHITE,
                                padding=20,
                                border_radius=12,
                                border=ft.border.all(1, "#e5e7eb"),
                                shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK)),
                            ),
                            
                            # Confidence filter section
                            ft.Container(height=15),
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Icon(ft.Icons.ANALYTICS, size=20, color="#8b5cf6"),
                                                ft.Text("Study by Confidence", size=15, weight=ft.FontWeight.W_600, color="#1f2937"),
                                            ],
                                            spacing=8,
                                        ),
                                        ft.Text("Review cards based on difficulty", size=12, color="#6b7280"),
                                        ft.Container(height=10),
                                        confidence_buttons,
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                bgcolor=ft.Colors.WHITE,
                                padding=20,
                                border_radius=12,
                                border=ft.border.all(1, "#e5e7eb"),
                                shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK)),
                            ),
                            
                            # Chapter selection section
                            ft.Container(height=15),
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Icon(ft.Icons.MENU_BOOK, size=20, color="#f59e0b"),
                                                ft.Text("Study by Chapter", size=15, weight=ft.FontWeight.W_600, color="#1f2937"),
                                            ],
                                            spacing=8,
                                        ),
                                        ft.Text("Select chapters to review", size=12, color="#6b7280"),
                                        ft.Container(height=10),
                                        chapter_section,
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                bgcolor=ft.Colors.WHITE,
                                padding=20,
                                border_radius=12,
                                border=ft.border.all(1, "#e5e7eb"),
                                shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK)),
                            ),
                            ft.Container(height=30),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        scroll=ft.ScrollMode.AUTO
                    ),
                    alignment=ft.Alignment(0, 0),
                    expand=True,
                    padding=ft.padding.symmetric(horizontal=20, vertical=10),
                    bgcolor="#f9fafb",
                )
            ]
        )

    def get_study_view():
        # State for this view
        is_flipped = False
        current_card = app_state.get_next_card()
        
        if not current_card:
            # Session Complete View
            return ft.View(
                "/study",
                [
                    ft.AppBar(
                        title=ft.Text("Study Session"),
                        bgcolor=ft.Colors.WHITE,
                        leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: page.go("/"))
                    ),
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(ft.Icons.CELEBRATION, size=72, color="#10b981"),
                                ft.Text("Session Complete!", size=28, weight=ft.FontWeight.BOLD, color="#1f2937"),
                                ft.Text(f"You reviewed {app_state.session_stats['reviewed']} cards", size=16, color="#6b7280"),
                                ft.Container(height=20),
                                ft.ElevatedButton(
                                    "Back to Menu",
                                    icon=ft.Icons.HOME,
                                    style=ft.ButtonStyle(
                                        bgcolor="#6366f1",
                                        color="#ffffff",
                                        padding=16,
                                        shape=ft.RoundedRectangleBorder(radius=10),
                                    ),
                                    on_click=lambda _: page.go("/")
                                )
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER
                        ),
                        alignment=ft.Alignment(0, 0),
                        expand=True,
                        bgcolor="#f9fafb",
                    )
                ],
                bgcolor="#f9fafb",
            )

        # UI Elements
        progress_val = 0
        if app_state.session_stats['total_due'] > 0:
            progress_val = app_state.session_stats['reviewed'] / app_state.session_stats['total_due']
            
        progress_bar = ft.ProgressBar(value=progress_val, height=6, color="#6366f1", bgcolor="#e5e7eb")
        
        # Focus sink container - Invisible element that helps with keyboard focus
        # Using a Container instead of ElevatedButton to avoid Flet's assertion error
        focus_sink_button = ft.Container(
            width=0,
            height=0,
        )
        
        # Card Content - with explicit dark text color for visibility
        front_text = ft.Text(
            str(current_card.get('front', 'Error')), 
            size=24, 
            text_align=ft.TextAlign.CENTER,
            color=ft.Colors.BLACK
        )
        back_text = ft.Text(
            str(current_card.get('back', 'Error')), 
            size=24, 
            text_align=ft.TextAlign.CENTER,
            color=ft.Colors.BLACK
        )
        
        card_content = ft.Container(
            content=front_text,
            alignment=ft.Alignment(0, 0),
            padding=20,
            expand=True
        )
        
        
        # Current rating value (stored for keyboard shortcuts)
        current_rating = [3]  # Use list for mutability in closures
        
        # Rating button colors and labels
        rating_config = {
            1: {"color": ft.Colors.RED_400, "label": "😟 1", "desc": "Hard"},
            2: {"color": ft.Colors.ORANGE_400, "label": "😕 2", "desc": "Difficult"},
            3: {"color": ft.Colors.YELLOW_600, "label": "😐 3", "desc": "So-so"},
            4: {"color": ft.Colors.LIGHT_GREEN_400, "label": "🙂 4", "desc": "Good"},
            5: {"color": ft.Colors.GREEN_400, "label": "😊 5", "desc": "Easy"},
        }
        
        # Create rating buttons
        rating_buttons = []
        selected_button_ref = [None]
        
        def on_rating_click(rating):
            def handler(e):
                current_rating[0] = rating
                # Update button selection visuals
                for i, btn in enumerate(rating_buttons, 1):
                    if i == rating:
                        btn.style = ft.ButtonStyle(
                            bgcolor=rating_config[i]["color"],
                            color=ft.Colors.WHITE,
                            side=ft.BorderSide(3, ft.Colors.BLACK)
                        )
                    else:
                        btn.style = ft.ButtonStyle(
                            bgcolor=rating_config[i]["color"],
                            color=ft.Colors.WHITE
                        )
                page.update()
            return handler
        
        for i in range(1, 6):
            btn = ft.ElevatedButton(
                rating_config[i]["label"],
                bgcolor=rating_config[i]["color"],
                color=ft.Colors.WHITE,
                on_click=on_rating_click(i),
                style=ft.ButtonStyle(
                    bgcolor=rating_config[i]["color"],
                    color=ft.Colors.WHITE,
                    side=ft.BorderSide(3, ft.Colors.BLACK) if i == 3 else None
                ),
                width=80,
                height=50
            )
            rating_buttons.append(btn)
        
        # Copy to Gemini function
        def copy_to_gemini(e):
            question = str(current_card.get('front', ''))
            answer = str(current_card.get('back', ''))
            
            prompt = f"""Explain this question and answer in detail:

**QUESTION:** {question}

**ANSWER:** {answer}

Please provide:
1. A thorough explanation of the concept
2. Practical examples if applicable
3. Connections to related topics
4. Key points to remember"""
            
            page.set_clipboard(prompt)
            page.snack_bar = ft.SnackBar(
                ft.Text("📋 Copied! Paste to Gemini for detailed explanation"),
                bgcolor=ft.Colors.GREEN_600
            )
            page.snack_bar.open = True
            page.update()
        
        # Chapter dropdown (only visible in chapter mode when flipped)
        current_chapter = current_card.get('chapter', 1)
        
        def on_chapter_change(e):
            new_chapter = int(e.control.value)
            if app_state.update_card_chapter(new_chapter):
                page.snack_bar = ft.SnackBar(
                    ft.Text(f"✅ Card moved to Chapter {new_chapter}: {CHAPTER_NAMES.get(new_chapter, '')}"),
                    bgcolor=ft.Colors.GREEN_600
                )
                page.snack_bar.open = True
                page.update()
        
        chapter_dropdown = ft.Dropdown(
            label="Move to Chapter",
            value=str(int(current_chapter) if pd.notna(current_chapter) else 1),
            options=[
                ft.dropdown.Option(str(i), f"Ch. {i}: {CHAPTER_NAMES.get(i, '')}")
                for i in range(1, 8)
            ],
            width=300,
            on_change=on_chapter_change
        )
        
        chapter_row = ft.Row(
            [chapter_dropdown],
            alignment=ft.MainAxisAlignment.CENTER,
            visible=False  # Will be shown only in chapter mode when flipped
        )
        
        # Edit answer function
        def edit_answer(e):
            answer_field = ft.TextField(
                value=str(current_card.get('back', '')),
                multiline=True,
                min_lines=3,
                max_lines=10,
                width=500
            )
            
            def save_edit(ev):
                if app_state.update_card_answer(answer_field.value):
                    current_card['back'] = answer_field.value
                    if is_flipped:
                        back_text.value = answer_field.value
                    page.close(dlg)
                    page.snack_bar = ft.SnackBar(
                        ft.Text("✅ Risposta aggiornata!"),
                        bgcolor=ft.Colors.GREEN_600
                    )
                    page.snack_bar.open = True
                    page.update()
            
            dlg = ft.AlertDialog(
                title=ft.Text("Modifica Risposta"),
                content=answer_field,
                actions=[
                    ft.TextButton("Annulla", on_click=lambda ev: page.close(dlg)),
                    ft.ElevatedButton("Salva", on_click=save_edit),
                ]
            )
            page.open(dlg)
        
        # Remove card function
        def remove_card(e):
            if app_state.remove_current_card():
                page.snack_bar = ft.SnackBar(
                    ft.Text("🗑️ Card removed - won't appear again"),
                    bgcolor=ft.Colors.ORANGE_600
                )
                page.snack_bar.open = True
                # Reload view to show next card
                page.views.pop()
                page.views.append(get_study_view())
                page.update()
        
        # Controls Container (Hidden initially)
        controls = ft.Column(
            [
                ft.Text("How confident do you feel?", weight=ft.FontWeight.BOLD, size=16),
                ft.Container(height=10),
                ft.Row(
                    rating_buttons,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10
                ),
                ft.Container(height=15),
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "Confirm (Enter)",
                            icon=ft.Icons.CHECK,
                            style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY),
                            width=180,
                            height=45,
                            on_click=lambda e: confirm_review(e)
                        ),
                        ft.OutlinedButton(
                            "📋 Copy to Gemini",
                            icon=ft.Icons.COPY,
                            width=180,
                            height=45,
                            on_click=copy_to_gemini
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=15
                ),
                ft.Container(height=10),
                ft.Row(
                    [
                        ft.OutlinedButton(
                            "✏️ Modifica Risposta",
                            icon=ft.Icons.EDIT,
                            width=180,
                            height=40,
                            style=ft.ButtonStyle(color=ft.Colors.BLUE_600),
                            on_click=edit_answer
                        ),
                        ft.OutlinedButton(
                            "🗑️ Remove Card",
                            icon=ft.Icons.DELETE_OUTLINE,
                            width=180,
                            height=40,
                            style=ft.ButtonStyle(color=ft.Colors.RED_400),
                            on_click=remove_card
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=15
                ),
                ft.Container(height=10),
                chapter_row,
                ft.Container(height=10),
                ft.Text(
                    "⌨️ Space = Flip | ←→ = Navigate Cards | 1-5 = Rating | Enter = Confirm",
                    size=11,
                    color=ft.Colors.OUTLINE,
                    italic=True
                )
            ],
            visible=False,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )

        def flip_card(e=None):
            nonlocal is_flipped
            is_flipped = not is_flipped
            
            # Animate switch
            card_container.content.content = back_text if is_flipped else front_text
            card_container.bgcolor = ft.Colors.BLUE_GREY_50 if is_flipped else ft.Colors.WHITE
            
            # Update card label
            card_label.value = "ANSWER" if is_flipped else "QUESTION"
            card_label.color = ft.Colors.BLUE_600 if is_flipped else ft.Colors.GREY_600
            
            # Show controls if flipped
            controls.visible = is_flipped
            
            # Show chapter dropdown only in chapter mode when flipped
            chapter_row.visible = is_flipped and app_state.current_study_mode == "chapter"
            
            page.update()

        # Card label indicator
        card_label = ft.Text("QUESTION", size=12, weight=ft.FontWeight.BOLD, color="#6366f1")

        card_container = ft.Container(
            content=card_content,
            width=700,
            height=350,
            bgcolor="#ffffff",
            border_radius=20,
            border=ft.border.all(1, "#e2e8f0"),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=30,
                color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
                offset=ft.Offset(0, 8),
                blur_style=ft.ShadowBlurStyle.OUTER,
            ),
            padding=40,
            on_click=flip_card,
            animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
        )

        def confirm_review(e=None):
            quality = current_rating[0]
            app_state.process_review(quality)
            # Reload view to show next card
            page.views.pop()
            page.views.append(get_study_view())
            page.update()
        
        # Keyboard event handler - Always update page to consume events and prevent macOS error sound
        def on_keyboard(e: ft.KeyboardEvent):
            nonlocal is_flipped
            key = e.key
            handled = True  # Track if we handled the key
            
            # Spacebar to flip
            if key == " ":
                flip_card()
                return  # flip_card already calls page.update()
            # Enter to confirm (only if flipped)
            elif key == "Enter" and is_flipped:
                confirm_review()
                return  # confirm_review handles its own update
            # Number keys 1-5 to set rating (only if flipped)
            elif key in "12345" and is_flipped:
                rating = int(key)
                on_rating_click(rating)(None)
                return  # on_rating_click handles update
            # Arrow keys to navigate cards (without reviewing)
            elif key == "Arrow Right":
                new_card = app_state.navigate_card(1)
                if new_card:
                    page.views.pop()
                    page.views.append(get_study_view())
                else:
                    page.snack_bar = ft.SnackBar(
                        ft.Text("📍 Last card in queue"),
                        bgcolor=ft.Colors.AMBER
                    )
                    page.snack_bar.open = True
            elif key == "Arrow Left":
                new_card = app_state.navigate_card(-1)
                if new_card:
                    page.views.pop()
                    page.views.append(get_study_view())
                else:
                    page.snack_bar = ft.SnackBar(
                        ft.Text("📍 First card in queue"),
                        bgcolor=ft.Colors.AMBER
                    )
                    page.snack_bar.open = True
            # C key to copy to Gemini
            elif key.lower() == "c" and is_flipped:
                copy_to_gemini(None)
                return  # copy_to_gemini handles update
            
            # Always call page.update() to ensure event is "consumed" by Flet
            # This helps prevent the macOS error sound for unhandled keys
            page.update()
        
        page.on_keyboard_event = on_keyboard 

        return ft.View(
            "/study",
            [
                ft.AppBar(
                    title=ft.Text("Study Mode"),
                    bgcolor=ft.Colors.WHITE,
                    leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: page.go("/")),
                ),
                focus_sink_button,  # Invisible button to capture keyboard focus and prevent macOS beep
                ft.Container(content=progress_bar, padding=ft.Padding(20, 10, 20, 10), bgcolor="#f9fafb"),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Container(
                                        content=ft.Text(f"Card {app_state.queue_position + 1} / {len(app_state.study_queue)}", 
                                               color="#374151", size=13),
                                        bgcolor="#f3f4f6",
                                        padding=ft.padding.symmetric(horizontal=12, vertical=6),
                                        border_radius=15,
                                    ),
                                    ft.Container(width=15),
                                    card_label,
                                ],
                                alignment=ft.MainAxisAlignment.CENTER
                            ),
                            ft.Container(height=15),
                            card_container,
                            ft.Text("👆 Click or press Space to flip", italic=True, color="#6b7280", size=12),
                            ft.Container(height=15),
                            controls
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    alignment=ft.alignment.center,
                    expand=True,
                    bgcolor="#f9fafb",
                )
            ],
            bgcolor="#f9fafb",
        )

    def route_change(route):
        page.views.clear()
        if page.route == "/":
            page.views.append(get_home_view())
        elif page.route == "/study":
            page.views.append(get_study_view())
        page.update()

    def view_pop(view):
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    
    page.go(page.route)

if __name__ == "__main__":
    ft.app(target=main)
