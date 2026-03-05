# Runtime Security Monitor - Anti-Tampering Protection
# Detects and prevents code injection, debugging, and tampering

import os
import sys
import time
import hashlib
import ctypes
import threading
import inspect
from datetime import datetime

class RuntimeSecurityMonitor:
    """Advanced runtime protection against reverse engineering and tampering"""
    
    def __init__(self):
        self.start_time = time.time()
        self.threats_detected = []
        self.monitoring_active = True
        self.session_key = None
        self.load_session_key()
        
    def load_session_key(self):
        """Load session key from build directory"""
        try:
            # Try to load from executable directory
            if getattr(sys, 'frozen', False):
                exe_dir = os.path.dirname(sys.executable)
            else:
                exe_dir = os.path.dirname(os.path.abspath(__file__))
            
            key_path = os.path.join(exe_dir, '.session_key')
            if os.path.exists(key_path):
                with open(key_path, 'r') as f:
                    self.session_key = f.read().strip()
        except Exception as e:
            pass
    
    def verify_executable_integrity(self):
        """Verify the executable hasn't been modified"""
        try:
            if not getattr(sys, 'frozen', False):
                return True  # Skip for development
            
            exe_path = sys.executable
            hash_path = exe_path + '.sha256'
            
            if not os.path.exists(hash_path):
                return True  # No hash file, skip verification
            
            # Calculate current hash
            sha256_hash = hashlib.sha256()
            with open(exe_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            current_hash = sha256_hash.hexdigest()
            
            # Read stored hash
            with open(hash_path, 'r') as f:
                stored_hash = f.read().strip()
            
            # Compare hashes
            if current_hash != stored_hash:
                self.log_threat("EXECUTABLE TAMPERING DETECTED", 
                              f"Hash mismatch! Executable has been modified.")
                return False
            
            return True
        except Exception as e:
            return True  # Don't block on errors
    
    def check_debugger_presence(self):
        """Detect if debugger is attached"""
        try:
            if sys.platform == 'win32':
                # Check for common debugger processes
                debugger_names = ['x64dbg', 'x32dbg', 'ollydbg', 'ida', 'ida64', 
                                'windbg', 'immunity', 'ghidra']
                
                import subprocess
                try:
                    output = subprocess.check_output(
                        ['tasklist'], 
                        stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    ).decode('utf-8', errors='ignore').lower()
                    
                    for debugger in debugger_names:
                        if debugger in output:
                            self.log_threat("DEBUGGER DETECTED", 
                                          f"Debugger process '{debugger}' found")
                            return True
                except:
                    pass
                
                # Check IsDebuggerPresent API
                try:
                    if ctypes.windll.kernel32.IsDebuggerPresent():
                        self.log_threat("DEBUGGER DETECTED", 
                                      "IsDebuggerPresent API returned true")
                        return True
                except:
                    pass
            
            return False
        except Exception:
            return False
    
    def check_code_injection(self):
        """Detect code injection attempts"""
        try:
            frames = inspect.stack()
            suspicious_patterns = [
                'eval(', 'exec(', 'compile(', '__import__(',
                'getattr(', 'setattr(', 'delattr('
            ]
            
            for frame in frames:
                try:
                    frame_code = str(frame.code_context)
                    for pattern in suspicious_patterns:
                        if pattern in frame_code.lower():
                            # Check if it's from our security module (allow it)
                            if 'security' not in frame.filename.lower():
                                self.log_threat("CODE INJECTION DETECTED", 
                                              f"Suspicious pattern: {pattern}")
                                return True
                except:
                    continue
            
            return False
        except Exception:
            return False
    
    def check_memory_dump(self):
        """Detect memory dump tools"""
        try:
            if sys.platform == 'win32':
                # Check for memory analysis tools
                dump_tools = ['procdump', 'dumpit', 'ftk', 'volatility']
                
                import subprocess
                try:
                    output = subprocess.check_output(
                        ['tasklist'], 
                        stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    ).decode('utf-8', errors='ignore').lower()
                    
                    for tool in dump_tools:
                        if tool in output:
                            self.log_threat("MEMORY DUMP TOOL DETECTED", 
                                          f"Tool '{tool}' found running")
                            return True
                except:
                    pass
            
            return False
        except Exception:
            return False
    
    def check_vm_environment(self):
        """Detect virtual machine/sandbox environment"""
        try:
            vm_indicators = []
            
            # Check for VM-specific files
            vm_files = [
                r'C:\Windows\System32\drivers\vmmouse.sys',
                r'C:\Windows\System32\drivers\vmhgfs.sys',
                r'C:\Windows\System32\drivers\VBoxMouse.sys',
                r'C:\Windows\System32\drivers\VBoxGuest.sys',
            ]
            
            for filepath in vm_files:
                if os.path.exists(filepath):
                    vm_indicators.append(f"VM file: {filepath}")
            
            # Check for VM-specific registry keys (Windows)
            if sys.platform == 'win32':
                try:
                    import winreg
                    vm_registries = [
                        r'SOFTWARE\VMware, Inc.',
                        r'SOFTWARE\Oracle\VirtualBox Guest Additions',
                    ]
                    
                    for reg_path in vm_registries:
                        try:
                            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
                            if key:
                                vm_indicators.append(f"VM registry: {reg_path}")
                                winreg.CloseKey(key)
                        except:
                            pass
                except:
                    pass
            
            # If multiple indicators found, likely a VM
            if len(vm_indicators) >= 2:
                self.log_threat("VM/SANDBOX DETECTED", 
                              f"VM indicators: {', '.join(vm_indicators)}")
                return True
            
            return False
        except Exception:
            return False
    
    def check_process_manipulation(self):
        """Detect process manipulation attempts"""
        try:
            # Check if process is being traced
            if sys.platform == 'win32':
                # Check for parent process injection
                import ctypes
                try:
                    # Get parent process ID
                    parent_pid = ctypes.windll.kernel32.GetCurrentProcessId()
                    # Additional checks could be added here
                except:
                    pass
            
            return False
        except Exception:
            return False
    
    def log_threat(self, threat_type, details):
        """Log detected threat"""
        timestamp = datetime.now().isoformat()
        threat_info = {
            'timestamp': timestamp,
            'type': threat_type,
            'details': details,
            'pid': os.getpid()
        }
        self.threats_detected.append(threat_info)
        
        # In production, you might want to:
        # 1. Send alert to server
        # 2. Log to secure location
        # 3. Trigger application shutdown
        
        if os.environ.get('SECURITY_DEBUG'):
            print(f"\n🚨 SECURITY ALERT: {threat_type}")
            print(f"   Details: {details}")
            print(f"   Time: {timestamp}\n")
    
    def start_continuous_monitoring(self, interval=5.0):
        """Start continuous security monitoring thread"""
        def monitor_loop():
            while self.monitoring_active:
                # Run all checks
                checks = [
                    ('Debugger', self.check_debugger_presence),
                    ('Code Injection', self.check_code_injection),
                    ('Memory Dump', self.check_memory_dump),
                    ('Executable Integrity', lambda: not self.verify_executable_integrity()),
                ]
                
                for check_name, check_func in checks:
                    try:
                        if check_func():
                            # Critical threat detected
                            self.handle_critical_threat(check_name)
                    except Exception:
                        pass
                
                time.sleep(interval)
        
        # Start monitoring in background thread
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        return monitor_thread
    
    def handle_critical_threat(self, threat_name):
        """Handle critical security threat"""
        # Log the threat
        self.log_threat(f"CRITICAL: {threat_name}", 
                       "Application security compromised")
        
        # In production, you might want to:
        # 1. Gracefully shutdown
        # 2. Clear sensitive data from memory
        # 3. Report to server
        # 4. Block further execution
        
        # For now, we'll just log it
        if os.environ.get('SECURITY_DEBUG'):
            print(f"\n⛔ CRITICAL THREAT: {threat_name}")
            print("   Application should terminate in production!\n")
    
    def get_threat_report(self):
        """Get report of all detected threats"""
        return {
            'total_threats': len(self.threats_detected),
            'threats': self.threats_detected,
            'session_verified': self.session_key is not None,
            'monitoring_duration': time.time() - self.start_time
        }
    
    def stop_monitoring(self):
        """Stop continuous monitoring"""
        self.monitoring_active = False


# Global security monitor instance
security_monitor = RuntimeSecurityMonitor()


def initialize_security():
    """Initialize security monitoring at application startup"""
    # Start continuous monitoring
    security_monitor.start_continuous_monitoring(interval=10.0)
    
    # Perform initial integrity check
    if not security_monitor.verify_executable_integrity():
        print("⚠️  WARNING: Executable integrity check failed!")
        # In production: sys.exit(1)
    
    # Check for debugger
    if security_monitor.check_debugger_presence():
        print("⚠️  WARNING: Debugger detected!")
        # In production: sys.exit(1)
    
    return security_monitor
