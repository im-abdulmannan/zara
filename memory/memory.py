import json
import os

# Store the history file in the same directory as this module
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "history.json")

def load_history():
    """
    Loads conversation history from the history.json file.
    Returns a list of message dicts or an empty list if file doesn't exist.
    """
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading memory: {e}")
        return []

def save_history(history, max_entries=100):
    """
    Saves conversation history to the history.json file.
    Truncates history to the last max_entries to prevent excessive growth.
    """
    try:
        if len(history) > max_entries:
            history = history[-max_entries:]
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving memory: {e}")
