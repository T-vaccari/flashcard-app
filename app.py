import os
import uuid
import math
import logging
import pathlib
from datetime import datetime, timedelta
import pandas as pd
from flask import Flask, request, jsonify, render_template

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# --- Global State (Single User Local App) ---
class AppState:
    def __init__(self):
        self.df = None
        self.current_file_path = None
        self.study_queue = []  # List of indices
        self.session_stats = {"reviewed": 0, "total_due": 0}

state = AppState()

# --- SM-2 Algorithm ---
def calculate_next_review(card: dict, quality: int) -> dict:
    """
    Implements the SuperMemo-2 (SM-2) algorithm.
    """
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

# --- Helper Functions ---
def save_data():
    """Saves the current DataFrame to Excel."""
    if state.df is not None and state.current_file_path:
        try:
            state.df.to_excel(state.current_file_path, index=False)
            logging.info(f"Saved data to {state.current_file_path}")
        except Exception as e:
            logging.error(f"Error saving data: {e}")

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/load', methods=['POST'])
def load_data():
    data = request.json
    file_path = data.get('file_path')
    
    if not file_path:
        return jsonify({"success": False, "message": "No file path provided"}), 400
        
    # Remove quotes if present
    file_path = file_path.strip().strip('"').strip("'")
    
    if not os.path.exists(file_path):
        return jsonify({"success": False, "message": "File not found"}), 404
        
    try:
        state.current_file_path = file_path
        # Read Excel
        state.df = pd.read_excel(file_path)
        
        # Ensure required columns
        required_columns = {
            'id': lambda: str(uuid.uuid4()),
            'front': '',
            'back': '',
            'last_review': '', 
            'interval': 0,
            'ease_factor': 2.5,
            'repetitions': 0
        }

        for col, default in required_columns.items():
            if col not in state.df.columns:
                if callable(default):
                    state.df[col] = [default() for _ in range(len(state.df))]
                else:
                    state.df[col] = default
                    
        # Fill NaNs
        state.df['interval'] = state.df['interval'].fillna(0).astype(int)
        state.df['ease_factor'] = state.df['ease_factor'].fillna(2.5).astype(float)
        state.df['repetitions'] = state.df['repetitions'].fillna(0).astype(int)
        state.df['last_review'] = state.df['last_review'].fillna('')
        
        # Generate IDs if missing
        if state.df['id'].isnull().any():
             state.df.loc[state.df['id'].isnull(), 'id'] = [str(uuid.uuid4()) for _ in range(state.df['id'].isnull().sum())]

        # Sorting Logic
        temp_last_review = pd.to_datetime(state.df['last_review'], errors='coerce')
        
        def calculate_due_date(row):
            if pd.isna(row['last_review_dt']):
                return datetime.min 
            return row['last_review_dt'] + timedelta(days=row['interval'])

        sort_df = state.df.copy()
        sort_df['last_review_dt'] = temp_last_review
        sort_df['due_date'] = sort_df.apply(calculate_due_date, axis=1)
        
        today = datetime.now()
        due_mask = sort_df['due_date'] <= today
        
        due_cards = sort_df[due_mask].sort_values(by='due_date', ascending=True)
        
        state.study_queue = due_cards.index.tolist()
        state.session_stats["total_due"] = len(state.study_queue)
        state.session_stats["reviewed"] = 0
        
        # Save immediately to ensure schema consistency
        save_data()
        
        return jsonify({
            "success": True, 
            "message": f"Loaded {len(state.study_queue)} cards due.",
            "stats": state.session_stats
        })

    except Exception as e:
        logging.error(f"Error loading file: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/next', methods=['GET'])
def get_next_card():
    if state.df is None:
        return jsonify({"error": "No data loaded"}), 400
        
    if not state.study_queue:
        return jsonify({"finished": True, "stats": state.session_stats})
        
    current_index = state.study_queue[0]
    card_data = state.df.loc[current_index].to_dict()
    
    # Handle NaN values for JSON serialization
    for k, v in card_data.items():
        if isinstance(v, float) and math.isnan(v):
            card_data[k] = ""
            
    return jsonify({
        "finished": False,
        "card": card_data,
        "stats": state.session_stats,
        "index": int(current_index) # Send index to identify card in review
    })

@app.route('/api/review', methods=['POST'])
def process_review():
    data = request.json
    index = data.get('index')
    quality = data.get('quality')
    
    if index is None or quality is None:
        return jsonify({"success": False, "message": "Missing index or quality"}), 400
        
    try:
        # Verify index matches head of queue (simple consistency check)
        if not state.study_queue or state.study_queue[0] != index:
            # If it doesn't match, we might have a sync issue, but we can still process it if valid
            logging.warning(f"Review index {index} does not match queue head {state.study_queue[0] if state.study_queue else 'Empty'}")
            
        card_data = state.df.loc[index].to_dict()
        updated_card = calculate_next_review(card_data, int(quality))
        
        # Update DataFrame
        for key, value in updated_card.items():
            if key in state.df.columns:
                state.df.at[index, key] = value
                
        # Save to disk
        save_data()
        
        # Remove from queue if it was there
        if index in state.study_queue:
            state.study_queue.remove(index)
            
        state.session_stats["reviewed"] += 1
        
        return jsonify({"success": True, "stats": state.session_stats})
        
    except Exception as e:
        logging.error(f"Error processing review: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)



