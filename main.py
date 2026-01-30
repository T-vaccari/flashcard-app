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
            temp_last_review = pd.to_datetime(self.df['last_review'], errors='coerce')
            
            def calculate_due_date(row):
                if pd.isna(row['last_review_dt']):
                    return datetime.min # Treat never reviewed as very old (high priority)
                return row['last_review_dt'] + timedelta(days=row['interval'])

            # Create a temporary dataframe for sorting
            sort_df = self.df.copy()
            sort_df['last_review_dt'] = temp_last_review
            sort_df['due_date'] = sort_df.apply(calculate_due_date, axis=1)
            
            today = datetime.now()
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
        return self.df.loc[self.current_card_index].to_dict()

    def navigate_card(self, direction: int):
        new_position = self.queue_position + direction
        if 0 <= new_position < len(self.study_queue):
            self.queue_position = new_position
            return self.get_next_card()
        return None

    def update_card_chapter(self, new_chapter: int):
        if self.current_card_index is not None and self.df is not None:
            self.df.at[self.current_card_index, 'chapter'] = new_chapter
            self.save_data()
            return True
        return False

    def remove_current_card(self):
        if self.current_card_index is not None and self.df is not None:
            self.df.at[self.current_card_index, 'removed'] = 1
            self.save_data()
            if self.queue_position < len(self.study_queue):
                self.study_queue.pop(self.queue_position)
                if self.queue_position >= len(self.study_queue):
                    self.queue_position = max(0, len(self.study_queue) - 1)
            self.current_card_index = None
            return True
        return False

    def update_card_answer(self, new_answer: str) -> bool:
        if self.current_card_index is None or self.df is None:
            return False
        self.df.at[self.current_card_index, 'back'] = new_answer
        self.df.at[self.current_card_index, 'risposta'] = new_answer
        self.save_data()
        return True

    def add_new_flashcard(self, question: str, answer: str, chapter: int = 1) -> bool:
        if self.df is None:
            return False
        new_card = {
            'domanda': question, 'risposta': answer, 'id': str(uuid.uuid4()),
            'front': question, 'back': answer, 'last_review': '',
            'interval': 0, 'ease_factor': 2.5, 'repetitions': 0,
            'last_confidence': 0, 'chapter': chapter, 'removed': 0
        }
        self.df = pd.concat([self.df, pd.DataFrame([new_card])], ignore_index=True)
        self.save_data()
        return True

    def process_review(self, quality: int):
        if self.current_card_index is None:
            return
        card_data = self.df.loc[self.current_card_index].to_dict()
        updated_card = calculate_next_review(card_data, quality)
        for key, value in updated_card.items():
            if key in self.df.columns:
                self.df.at[self.current_card_index, key] = value
        self.df.at[self.current_card_index, 'last_confidence'] = quality
        self.save_data()
        self.study_queue.pop(self.queue_position)
        self.session_stats["reviewed"] += 1
        if self.queue_position >= len(self.study_queue):
            self.queue_position = max(0, len(self.study_queue) - 1)
        self.current_card_index = None

    def get_confidence_counts(self):
        if self.df is None: return {i: 0 for i in range(6)}
        active_df = self.df[self.df['removed'] != 1]
        counts = active_df['last_confidence'].value_counts().to_dict()
        return {i: counts.get(i, 0) for i in range(6)}

    def load_by_confidence(self, file_path: str, confidence_level: int):
        success, message = self.load_data(file_path)
        if not success: return False, message
        filtered_indices = self.df[(self.df['last_confidence'] == confidence_level) & (self.df['removed'] != 1)].index.tolist()
        random.shuffle(filtered_indices)
        self.study_queue = filtered_indices
        self.session_stats["total_due"] = len(self.study_queue)
        self.session_stats["reviewed"] = 0
        self.queue_position = 0
        self.current_study_mode = "confidence"
        return True, f"Loaded {len(self.study_queue)} cards with confidence {confidence_level}"

    def get_chapter_counts(self):
        if self.df is None or 'chapter' not in self.df.columns: return {i: 0 for i in range(1, 8)}
        active_df = self.df[self.df['removed'] != 1]
        counts = active_df['chapter'].value_counts().to_dict()
        return {i: counts.get(i, 0) for i in range(1, 8)}

    def load_by_chapters(self, file_path: str, selected_chapters: list, study_mode: str = "cram"):
        success, message = self.load_data(file_path)
        if not success: return False, message
        if 'chapter' not in self.df.columns: return False, "No 'chapter' column found in CSV"
        
        if study_mode == "due":
            selected_chapters_set = set(selected_chapters)
            filtered_queue = [idx for idx in self.study_queue if self.df.at[idx, 'chapter'] in selected_chapters_set]
            self.study_queue = filtered_queue
            log_msg = f"due cards from chapters {selected_chapters}"
        else: 
            filtered_indices = self.df[(self.df['chapter'].isin(selected_chapters)) & (self.df['removed'] != 1)].index.tolist()
            random.shuffle(filtered_indices)
            self.study_queue = filtered_indices
            log_msg = f"cramming (all) cards from chapters {selected_chapters}"
        
        self.session_stats["total_due"] = len(self.study_queue)
        self.session_stats["reviewed"] = 0
        self.queue_position = 0
        self.current_study_mode = "chapter"
        logging.info(f"Filtered to {len(self.study_queue)} cards: {log_msg}")
        return True, f"Loaded {len(self.study_queue)} cards ({study_mode}) from {len(selected_chapters)} chapter(s)"

# --- UI Construction ---

def main(page: ft.Page):
    page.title = "Flashcard SRS App"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.theme = ft.Theme(color_scheme=ft.ColorScheme(primary="#6366f1", secondary="#8b5cf6", surface=ft.Colors.WHITE))
    app_state = FlashcardApp()
    DEFAULT_PATH = "flashcards.csv"

    def get_home_view():
        if pathlib.Path(DEFAULT_PATH).exists() and app_state.df is None:
            app_state.load_data(DEFAULT_PATH)
        
        # --- Shared Dialogs & Logic ---
        
        def start_study(success_cb):
            if success_cb():
                if app_state.study_queue:
                    page.go("/study")
                else:
                    page.snack_bar = ft.SnackBar(ft.Text("No cards found for this criteria!"), bgcolor=ft.Colors.AMBER)
                    page.snack_bar.open = True
                    page.update()
            
        def start_random_study(e):
             start_study(lambda: app_state.load_data(DEFAULT_PATH)[0])

        # Add Flashcard Dialog
        def open_add_dialog(e):
            q_field = ft.TextField(label="Domanda", multiline=True, min_lines=2, width=500)
            a_field = ft.TextField(label="Risposta", multiline=True, min_lines=3, width=500)
            ch_drop = ft.Dropdown(label="Capitolo", value="1", options=[ft.dropdown.Option(str(i), f"Ch. {i}") for i in range(1, 8)], width=500)
            
            def save(e):
                if not q_field.value or not a_field.value: return
                if app_state.add_new_flashcard(q_field.value, a_field.value, int(ch_drop.value)):
                    page.close(dlg)
                    page.snack_bar = ft.SnackBar(ft.Text("✅ Added!"), bgcolor=ft.Colors.GREEN)
                    page.snack_bar.open = True
                    # Refresh to update counts
                    page.views.clear()
                    page.views.append(get_home_view())
                    page.update()

            dlg = ft.AlertDialog(title=ft.Text("Add Flashcard"), content=ft.Column([q_field, a_field, ch_drop], tight=True), 
                                actions=[ft.TextButton("Cancel", on_click=lambda e: page.close(dlg)), ft.ElevatedButton("Save", on_click=save)])
            page.open(dlg)

        # Tab 1: Dashboard Content
        total = len(app_state.df) if app_state.df is not None else 0
        due = len(app_state.study_queue) if app_state.study_queue else 0
        
        tab_dashboard = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.AUTO_STORIES, size=64, color="#6366f1"),
                ft.Text(f"{total} Total Cards • {due} Due Now", size=16, color="#6b7280"),
                ft.Container(height=20),
                ft.ElevatedButton("Start Random Review", icon=ft.Icons.PLAY_ARROW, on_click=start_random_study, height=50, width=250),
                ft.Container(height=10),
                ft.OutlinedButton("Add New Card", icon=ft.Icons.ADD, on_click=open_add_dialog, height=50, width=250),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center, padding=40
        )

        # Tab 2: Chapters Content
        ch_counts = app_state.get_chapter_counts()
        selected_chs = {i: False for i in range(1, 8)}
        
        def on_ch_click(i):
            def h(e): selected_chs[i] = e.control.value; btn_start_ch.disabled = not any(selected_chs.values()); page.update()
            return h
            
        ch_list = ft.Column([ft.Checkbox(label=f"Ch.{i}: {CHAPTER_NAMES.get(i, '')} ({ch_counts.get(i,0)})", on_change=on_ch_click(i)) for i in range(1, 8)], scroll=ft.ScrollMode.AUTO, height=300)
        mode_radio = ft.RadioGroup(content=ft.Row([ft.Radio(value="cram", label="All (Cram)"), ft.Radio(value="due", label="Due Only")]), value="cram")
        
        def start_ch(e):
            chs = [k for k,v in selected_chs.items() if v]
            mode = mode_radio.value
            res, msg = app_state.load_by_chapters(DEFAULT_PATH, chs, study_mode=mode)
            if res:
                if app_state.study_queue: page.go("/study")
                else: page.snack_bar = ft.SnackBar(ft.Text(f"No cards found ({mode})"), bgcolor=ft.Colors.AMBER); page.snack_bar.open=True; page.update()
        
        btn_start_ch = ft.ElevatedButton("Study Selected", disabled=True, on_click=start_ch)
        
        tab_chapters = ft.Container(
            content=ft.Column([
                ft.Text("Select Chapters", size=20, weight=ft.FontWeight.BOLD),
                ch_list,
                ft.Divider(),
                ft.Text("Mode:"),
                mode_radio,
                ft.Container(height=10),
                btn_start_ch
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=30, alignment=ft.alignment.top_center
        )

        # Tab 3: Difficulty Content
        conf_counts = app_state.get_confidence_counts()
        colors = {1: ft.Colors.RED_400, 2: ft.Colors.ORANGE_400, 3: ft.Colors.YELLOW_600, 4: ft.Colors.LIGHT_GREEN_400, 5: ft.Colors.GREEN_400}
        labels = {1: "Hard", 2: "Diff", 3: "So-so", 4: "Good", 5: "Easy"}
        
        def load_conf(l):
            def h(e):
                res, msg = app_state.load_by_confidence(DEFAULT_PATH, l)
                if res and app_state.study_queue: page.go("/study")
                else: page.snack_bar = ft.SnackBar(ft.Text("No cards!"), bgcolor=ft.Colors.AMBER); page.snack_bar.open=True; page.update()
            return h

        conf_btns = [ft.ElevatedButton(f"{labels[i]} ({conf_counts.get(i,0)})", bgcolor=colors[i], color="white", on_click=load_conf(i), width=150) for i in range(1,6)]
        
        tab_confidence = ft.Container(
            content=ft.Column([
                ft.Text("Review by Difficulty", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(height=20),
                *conf_btns
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=40, alignment=ft.alignment.top_center
        )

        # Main Tabs Layout
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text="Dashboard", icon=ft.Icons.DASHBOARD, content=tab_dashboard),
                ft.Tab(text="Chapters", icon=ft.Icons.MENU_BOOK, content=tab_chapters),
                ft.Tab(text="Difficulty", icon=ft.Icons.ANALYTICS, content=tab_confidence),
            ],
            expand=True,
        )

        return ft.View("/", [tabs])

    def get_study_view():
        # Optimized Study View that updates in-place
        current_card = app_state.get_next_card()
        is_flipped = False
        current_rating = [3]

        # -- Controls --
        progress = ft.ProgressBar(value=0, color="#6366f1", bgcolor="#e5e7eb")
        
        txt_front = ft.Text("", size=24, text_align="center", color="black")
        txt_back = ft.Text("", size=24, text_align="center", color="black")
        lbl_card_type = ft.Text("QUESTION", size=12, weight="bold", color="#6366f1")
        
        card_inner = ft.Container(content=txt_front, alignment=ft.alignment.center, padding=20)
        card_container = ft.Container(
            content=card_inner, width=700, height=350, bgcolor="white", border_radius=20,
            border=ft.border.all(1, "#e2e8f0"),
            shadow=ft.BoxShadow(blur_radius=30, color=ft.Colors.with_opacity(0.1, "black")),
            padding=40, animate=ft.Animation(200, "easeOut")
        )

        ch_dropdown = ft.Dropdown(
            width=300, 
            options=[ft.dropdown.Option(str(i), f"Ch. {i}: {CHAPTER_NAMES.get(i, '')}") for i in range(1, 8)],
            text_size=12,
            content_padding=10
        )

        # Logic to update UI
        def update_ui():
            nonlocal is_flipped, current_card
            
            if not current_card:
                # Show complete state
                card_container.visible = False
                controls_col.visible = False
                done_container.visible = True
                page.update()
                return

            # Calc progress
            if app_state.session_stats['total_due'] > 0:
                progress.value = app_state.session_stats['reviewed'] / app_state.session_stats['total_due']

            # Update Texts
            txt_front.value = str(current_card.get('front', ''))
            txt_back.value = str(current_card.get('back', ''))
            
            # Update Chapter Dropdown
            curr_ch = current_card.get('chapter', 1)
            ch_dropdown.value = str(int(curr_ch)) if pd.notna(curr_ch) else "1"
            
            # Flip State
            if is_flipped:
                card_inner.content = txt_back
                card_container.bgcolor = "#f8fafc" # slight grey
                lbl_card_type.value = "ANSWER"
                controls_col.visible = True
            else:
                card_inner.content = txt_front
                card_container.bgcolor = "white"
                lbl_card_type.value = "QUESTION"
                controls_col.visible = False
            
            txt_counter.value = f"Card {app_state.queue_position + 1} / {len(app_state.study_queue)}"
            page.update()

        # Handlers
        def flip(e=None):
            nonlocal is_flipped
            is_flipped = not is_flipped
            update_ui()

        def next_c(e=None):
            nonlocal is_flipped, current_card
            res = app_state.navigate_card(1)
            if res: current_card = res; is_flipped = False; update_ui()

        def prev_c(e=None):
            nonlocal is_flipped, current_card
            res = app_state.navigate_card(-1)
            if res: current_card = res; is_flipped = False; update_ui()

        def confirm(e=None):
            nonlocal is_flipped, current_card
            app_state.process_review(current_rating[0])
            current_card = app_state.get_next_card()
            is_flipped = False
            current_rating[0] = 3
            update_ui()
            
        def on_ch_change(e):
            if app_state.update_card_chapter(int(e.control.value)):
                page.snack_bar = ft.SnackBar(ft.Text("Chapter Updated!"), bgcolor=ft.Colors.GREEN)
                page.snack_bar.open = True
                page.update()
                
        ch_dropdown.on_change = on_ch_change
        
        def copy_gemini(e):
             q, a = current_card.get('front'), current_card.get('back')
             page.set_clipboard(f"Explain:\nQ: {q}\nA: {a}")
             page.snack_bar = ft.SnackBar(ft.Text("Copied to clipboard!"), bgcolor=ft.Colors.GREEN); page.snack_bar.open=True; page.update()

        def edit_ans(e):
            tf = ft.TextField(value=str(current_card.get('back','')), multiline=True, min_lines=3, width=500)
            def save(e):
                if app_state.update_card_answer(tf.value):
                    current_card['back'] = tf.value
                    if is_flipped: txt_back.value = tf.value
                    page.close(dlg)
                    page.update()
            dlg = ft.AlertDialog(title=ft.Text("Edit Answer"), content=tf, actions=[ft.TextButton("Cancel", on_click=lambda e:page.close(dlg)), ft.ElevatedButton("Save", on_click=save)])
            page.open(dlg)

        def delete_card(e):
            if app_state.remove_current_card():
                nonlocal current_card, is_flipped
                # get_next_card will now return the *new* card at the current index (since old one popped)
                # But wait, remove_current_card pops it from queue.
                # So we just need to get card at current queue pos.
                current_card = app_state.get_next_card() 
                is_flipped = False
                page.snack_bar = ft.SnackBar(ft.Text("Card Deleted"), bgcolor=ft.Colors.ORANGE); page.snack_bar.open=True
                update_ui()

        # Ratings
        rating_btns = []
        rating_colors = {1:"#ef4444", 2:"#f97316", 3:"#eab308", 4:"#84cc16", 5:"#22c55e"}
        
        def set_rate(r):
            def h(e):
                current_rating[0] = r
                for i, b in enumerate(rating_btns, 1):
                    b.style = ft.ButtonStyle(bgcolor=rating_colors[i], color="white", side=ft.BorderSide(3, "black") if i==r else None)
                page.update()
            return h

        for i in range(1,6):
            rating_btns.append(ft.ElevatedButton(str(i), bgcolor=rating_colors[i], color="white", on_click=set_rate(i), width=50))

        # Layouts
        controls_col = ft.Column([
            ft.Text("Rate Confidence:", weight="bold"),
            ft.Row(rating_btns, alignment="center"),
            ft.Container(height=10),
            ft.ElevatedButton("CONFIRM REVIEW", icon=ft.Icons.CHECK, on_click=confirm, bgcolor="#6366f1", color="white", height=50, width=200),
            ft.Container(height=15),
            ft.Row([
                ft.OutlinedButton("Edit", icon=ft.Icons.EDIT, on_click=edit_ans),
                ft.OutlinedButton("Copy AI", icon=ft.Icons.COPY, on_click=copy_gemini),
                ft.OutlinedButton("Delete", icon=ft.Icons.DELETE, on_click=delete_card, style=ft.ButtonStyle(color="red")),
            ], alignment="center"),
            ft.Container(height=10),
            ft.Row([ft.Text("Move to:"), ch_dropdown], alignment="center")
        ], visible=False, horizontal_alignment="center")

        txt_counter = ft.Text("", color="grey")
        
        done_container = ft.Column([
            ft.Icon(ft.Icons.CELEBRATION, size=80, color="green"),
            ft.Text("Session Complete!", size=30, weight="bold"),
            ft.ElevatedButton("Back Home", on_click=lambda e: page.go("/"))
        ], visible=False, horizontal_alignment="center")

        card_container.on_click = flip

        # Keyboard
        def on_key(e: ft.KeyboardEvent):
            if e.key == " ": flip()
            elif e.key == "Arrow Right": next_c()
            elif e.key == "Arrow Left": prev_c()
            elif is_flipped and e.key == "Enter": confirm()
            elif is_flipped and e.key in "12345": set_rate(int(e.key))(None)
            page.update()

        page.on_keyboard_event = on_key

        # Initial Update
        update_ui() # This will set initial text

        return ft.View("/study", [
            ft.AppBar(title=ft.Text("Study Mode"), leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: page.go("/")), bgcolor="white"),
            ft.Container(content=progress, padding=ft.padding.symmetric(horizontal=20)),
            ft.Container(
                content=ft.Column([
                    ft.Container(height=20),
                    txt_counter,
                    lbl_card_type,
                    card_container,
                    ft.Container(height=20),
                    controls_col,
                    done_container
                ], horizontal_alignment="center"),
                alignment=ft.alignment.center, expand=True, bgcolor="#f9fafb"
            )
        ], bgcolor="#f9fafb")

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
    
    # Initialize the app by pushing the initial route
    page.push_route(page.route)

if __name__ == "__main__":
    ft.app(main)
