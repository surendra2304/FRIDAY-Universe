import ctypes
import subprocess
import time
import psutil

user32 = ctypes.windll.user32

def find_notepad_windows():
    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    GetWindowText = user32.GetWindowTextW
    GetWindowTextLength = user32.GetWindowTextLengthW
    IsWindowVisible = user32.IsWindowVisible

    found = []
    def foreach_window(hwnd, lParam):
        if IsWindowVisible(hwnd):
            length = GetWindowTextLength(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                GetWindowText(hwnd, buff, length + 1)
                if 'notepad' in buff.value.lower():
                    found.append((hwnd, buff.value))
        return True

    EnumWindows(EnumWindowsProc(foreach_window), 0)
    return found

def launch_and_foreground_notepad():
    # 1. Kill old notepads
    for p in psutil.process_iter(['name']):
        if p.info['name'] and 'notepad' in p.info['name'].lower():
            try:
                p.kill()
            except Exception:
                pass
    time.sleep(1)

    # 2. Launch notepad using cmd /c start notepad.exe
    subprocess.Popen(["cmd.exe", "/c", "start", "notepad.exe"], shell=False)
    time.sleep(2)

    # 3. Find HWND and bring to foreground
    windows = find_notepad_windows()
    print("Found windows:", windows)
    for hwnd, title in windows:
        user32.ShowWindow(hwnd, 9) # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        user32.SwitchToThisWindow(hwnd, True)
        print(f"Brought window to front: {hwnd} - {title}")

if __name__ == "__main__":
    launch_and_foreground_notepad()
