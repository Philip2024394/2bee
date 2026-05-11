"""
Keep Windows awake while jarvis is running so 2b can keep learning 24/7.

Uses SetThreadExecutionState (Win32 API) — the same mechanism PowerPoint and
video players use to prevent the screen from sleeping during playback.

Idempotent: calling acquire() twice does nothing extra; calling release()
twice does nothing extra. Safe to no-op on non-Windows platforms.
"""

import platform
import ctypes


# Flags from winbase.h
ES_CONTINUOUS = 0x80000000        # Inform the system that the state should remain in effect
ES_SYSTEM_REQUIRED = 0x00000001   # System (CPU) stays awake
ES_DISPLAY_REQUIRED = 0x00000002  # Display stays on
ES_AWAYMODE_REQUIRED = 0x00000040 # AwayMode (Vista+) — runs as if user is present

_active = False


def is_windows():
    return platform.system().lower() == "windows"


def acquire(keep_display_on=False):
    """Tell Windows: don't sleep while jarvis is running. By default the CPU
    stays awake but the display can still turn off (saves screen burn-in).
    Pass keep_display_on=True for full display-always-on."""
    global _active
    if not is_windows():
        return False
    if _active:
        return True
    flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
    if keep_display_on:
        flags |= ES_DISPLAY_REQUIRED
    try:
        result = ctypes.windll.kernel32.SetThreadExecutionState(flags)
        if result == 0:
            return False
        _active = True
        return True
    except Exception:
        return False


def release():
    """Restore default Windows sleep/idle behavior."""
    global _active
    if not is_windows() or not _active:
        return
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        _active = False
    except Exception:
        pass


def status():
    return {
        "platform": platform.system(),
        "supported": is_windows(),
        "active": _active,
    }
