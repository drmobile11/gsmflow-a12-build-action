# utils/helpers.py
import subprocess
import os
import sys
import ctypes

def run_subprocess_no_console(cmd, timeout=30, capture_output=True):
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    creationflags = subprocess.CREATE_NO_WINDOW

    result = subprocess.run(
        cmd,
        startupinfo=startupinfo,
        creationflags=creationflags,
        stdout=subprocess.PIPE if capture_output else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture_output else subprocess.DEVNULL,
        stdin=subprocess.PIPE,
        timeout=timeout,
        text=capture_output
    )
    return result

def get_lib_path(filename):
    """Get path to libs folder - works for script, PyInstaller exe, and Nuitka exe"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable (PyInstaller or Nuitka)
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller
            exe_dir = sys._MEIPASS
        else:
            # Nuitka - executable is in build directory
            exe_dir = os.path.dirname(sys.executable)
        
        lib_path = os.path.join(exe_dir, 'libs', filename)
        
        # If not found in bundled libs, try current directory
        if not os.path.exists(lib_path):
            lib_path = os.path.join(os.getcwd(), 'libs', filename)
        
        return lib_path
    else:
        # Running as script - libs folder is in project root
        base_path = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(base_path, 'libs', filename)

def hide_console():
    if sys.platform == "win32":
        whnd = ctypes.windll.kernel32.GetConsoleWindow()
        if whnd != 0:
            ctypes.windll.user32.ShowWindow(whnd, 0)
            ctypes.windll.kernel32.CloseHandle(whnd)