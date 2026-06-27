import os

def read_file(filepath):
    """
    Reads the content of a file.
    Returns (success_bool, content_or_error_message).
    """
    try:
        if not os.path.exists(filepath):
            return False, f"File {filepath} does not exist."
        with open(filepath, "r", encoding="utf-8") as f:
            return True, f.read()
    except Exception as e:
        return False, f"Error reading file: {str(e)}"

def write_file(filepath, content):
    """
    Writes content to a file.
    Returns (success_bool, status_message).
    """
    try:
        # Create directories if they do not exist
        directory = os.path.dirname(filepath)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return True, f"Successfully wrote to {filepath}."
    except Exception as e:
        return False, f"Error writing file: {str(e)}"
