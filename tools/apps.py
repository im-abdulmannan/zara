import os

def open_app(app_name):
    """
    Opens a local application on Windows.
    Returns (success_bool, app_display_name).
    """
    app_name = app_name.lower().strip()
    
    if app_name in ("chrome", "google chrome"):
        os.system("start chrome")
        return True, "Chrome"
    elif app_name in ("vscode", "vs code", "visual studio code"):
        os.system("code")
        return True, "VS Code"
    elif app_name in ("notepad", "editor"):
        os.system("start notepad")
        return True, "Notepad"
    elif app_name in ("calculator", "calc"):
        os.system("start calc")
        return True, "Calculator"
    else:
        # Fallback: attempt to execute start directly
        os.system(f"start {app_name}")
        return True, app_name
