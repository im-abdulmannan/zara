import os
from datetime import datetime


def lock_pc() -> None:
    """Lock the workstation."""
    os.system("rundll32.exe user32.dll,LockWorkStation")


def shutdown_pc() -> None:
    """Shut down the PC in 10 seconds."""
    os.system("shutdown /s /t 10")


def restart_pc() -> None:
    """Restart the PC in 10 seconds."""
    os.system("shutdown /r /t 10")


def get_current_time() -> str:
    """Return the current formatted system time."""
    return datetime.now().strftime("%I:%M %p")
