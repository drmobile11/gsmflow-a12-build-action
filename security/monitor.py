# security/monitor.py
import os
import time
import inspect
import threading
import ctypes
import winreg

DETECTED_THREATS = []

class SecurityMonitor:
    def __init__(self):
        self.suspicious_activities = []
        self.start_time = time.time()

    def check_code_injection(self):
        try:
            frames = inspect.stack()
            for frame in frames:
                if any(k in str(frame.code_context) for k in ['eval', 'exec', 'compile', '__import__']):
                    self.log_threat("Potential code injection", frame)
                    return True
        except: pass
        return False

    def check_api_sniffing(self):
        """Check for unauthorized API access attempts"""
        try:
            current = inspect.currentframe()
            for frame_info in inspect.getouterframes(current):
                frame_str = str(frame_info.frame.f_locals)
                # Check for attempts to access sensitive patterns
                if 'bot_token' in frame_str.lower() or 'api_key' in frame_str.lower():
                    self.log_threat("Unauthorized credential access attempt", frame_info)
                    return True
        except: pass
        return False

    def check_proxy_usage(self):
        proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']
        for var in proxy_vars:
            if os.environ.get(var):
                self.log_threat(f"Proxy env var: {var}", None)
                return True
        if os.name == 'nt':
            try:
                key = winreg.OpenKey(winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER),
                                   r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
                if winreg.QueryValueEx(key, "ProxyEnable")[0]:
                    self.log_threat("Windows proxy enabled", None)
                    return True
            except: pass
        return False

    def log_threat(self, message, frame_info):
        threat = {'message': message, 'timestamp': time.time(), 'frame': str(frame_info)}
        DETECTED_THREATS.append(threat)
        self.send_security_alert(threat)
        self.protective_action()

    def send_security_alert(self, threat_info):
        """Send security alert via server API (no direct Telegram)"""
        try:
            # Import here to avoid circular dependency
            from core.api import Api
            msg = f"SECURITY ALERT: {threat_info['message']} at {time.ctime(threat_info['timestamp'])}"
            Api.send_notification(
                type="security_alert",
                sn="SECURITY",
                message=msg
            )
        except: pass

    def protective_action(self):
        print("SECURITY THREAT - EXITING")
        os._exit(1)

    def continuous_monitoring(self):
        while True:
            if self.check_code_injection() or self.check_api_sniffing() or self.check_proxy_usage():
                break
            time.sleep(5)

security_monitor = SecurityMonitor()

def start_security_thread():
    t = threading.Thread(target=security_monitor.continuous_monitoring, daemon=True)
    t.start()

def anti_debug():
    try:
        if ctypes.windll.kernel32.IsDebuggerPresent():
            os._exit(1)
    except: pass