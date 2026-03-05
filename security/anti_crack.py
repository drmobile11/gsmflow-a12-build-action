# Anti-Cracking Protection - Prevents unauthorized activation
# Multiple layers of protection against serial key bypass

import os
import sys
import hashlib
import hmac
import time
import json
import base64
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class ActivationSecurity:
    """Advanced protection against activation bypass and cracking"""
    
    def __init__(self):
        # Master key for encryption (should be obfuscated in production)
        self.master_salt = b'A12Bypass_Secure_Salt_2024'
        self.encryption_key = None
        self.activation_cache = {}
        self.failed_attempts = 0
        self.max_failed_attempts = 5
        self.lockout_time = 300  # 5 minutes
        
        # Hardware fingerprint
        self.hardware_id = self.get_hardware_fingerprint()
        
        # Initialize encryption
        self.initialize_encryption()
    
    def get_hardware_fingerprint(self):
        """Generate unique hardware ID to bind activation"""
        try:
            if sys.platform == 'win32':
                import subprocess
                # Get CPU ID
                try:
                    output = subprocess.check_output(
                        ['wmic', 'cpu', 'get', 'ProcessorId'],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        stderr=subprocess.DEVNULL
                    ).decode('utf-8', errors='ignore')
                    cpu_id = ''.join(output.split()[1:2]) if output.split() else 'unknown'
                except:
                    cpu_id = 'unknown'
                
                # Get motherboard ID
                try:
                    output = subprocess.check_output(
                        ['wmic', 'baseboard', 'get', 'SerialNumber'],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        stderr=subprocess.DEVNULL
                    ).decode('utf-8', errors='ignore')
                    mobo_id = ''.join(output.split()[1:2]) if output.split() else 'unknown'
                except:
                    mobo_id = 'unknown'
                
                # Create fingerprint
                fingerprint = f"{cpu_id}_{mobo_id}_A12Bypass"
                return hashlib.sha256(fingerprint.encode()).hexdigest()
        except Exception as e:
            pass
        
        # Fallback
        return hashlib.sha256(str(time.time()).encode()).hexdigest()[:32]
    
    def initialize_encryption(self):
        """Initialize encryption key from master salt"""
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self.master_salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(b'A12Bypass_Master_Key'))
            self.encryption_key = Fernet(key)
        except Exception as e:
            print(f"Encryption initialization failed: {e}")
    
    def encrypt_activation_data(self, data):
        """Encrypt activation data"""
        if not self.encryption_key:
            return None
        
        try:
            json_data = json.dumps(data).encode('utf-8')
            encrypted = self.encryption_key.encrypt(json_data)
            return base64.b64encode(encrypted).decode('utf-8')
        except Exception as e:
            return None
    
    def decrypt_activation_data(self, encrypted_data):
        """Decrypt activation data"""
        if not self.encryption_key:
            return None
        
        try:
            decoded = base64.b64decode(encrypted_data.encode('utf-8'))
            decrypted = self.encryption_key.decrypt(decoded)
            return json.loads(decrypted.decode('utf-8'))
        except Exception as e:
            return None
    
    def generate_activation_signature(self, serial_key, device_id):
        """Generate HMAC signature for activation"""
        try:
            message = f"{serial_key}:{device_id}:{self.hardware_id}"
            signature = hmac.new(
                self.master_salt,
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            return signature
        except Exception:
            return None
    
    def verify_activation_signature(self, serial_key, device_id, signature):
        """Verify activation signature"""
        try:
            expected_signature = self.generate_activation_signature(serial_key, device_id)
            if not expected_signature:
                return False
            
            # Constant-time comparison to prevent timing attacks
            return hmac.compare_digest(expected_signature, signature)
        except Exception:
            return False
    
    def check_rate_limiting(self):
        """Check if too many failed attempts"""
        current_time = time.time()
        
        if self.failed_attempts >= self.max_failed_attempts:
            # Check if lockout period has passed
            last_attempt = self.activation_cache.get('last_attempt', 0)
            if current_time - last_attempt < self.lockout_time:
                remaining = int(self.lockout_time - (current_time - last_attempt))
                return False, f"Too many failed attempts. Try again in {remaining} seconds."
            else:
                # Reset after lockout
                self.failed_attempts = 0
        
        return True, "OK"
    
    def record_failed_attempt(self):
        """Record a failed activation attempt"""
        self.failed_attempts += 1
        self.activation_cache['last_attempt'] = time.time()
        
        if self.failed_attempts >= self.max_failed_attempts:
            # Log suspicious activity
            self.log_security_event("MULTIPLE_FAILED_ACTIVATIONS", 
                                  f"Failed attempts: {self.failed_attempts}")
    
    def reset_failed_attempts(self):
        """Reset failed attempts counter"""
        self.failed_attempts = 0
        self.activation_cache.pop('last_attempt', None)
    
    def validate_serial_format(self, serial_key):
        """Validate serial key format"""
        if not serial_key or len(serial_key) < 16:
            return False, "Invalid serial key format"
        
        # Check for common crack patterns
        crack_patterns = [
            '000000000000000',
            'AAAAAAAAAAAAAAA',
            'XXXXXXXXXXXXXXX',
            'TESTTESTTESTTEST',
            'CRACKEDCRACKEDC',
        ]
        
        for pattern in crack_patterns:
            if pattern in serial_key.upper():
                self.log_security_event("CRACK_PATTERN_DETECTED", 
                                      f"Pattern: {pattern}")
                return False, "Invalid serial key"
        
        return True, "OK"
    
    def activate_device(self, serial_key, device_udid):
        """
        Secure activation process with multiple checks
        Returns: (success, message, activation_data)
        """
        # Check rate limiting
        allowed, message = self.check_rate_limiting()
        if not allowed:
            return False, message, None
        
        # Validate serial format
        valid, message = self.validate_serial_format(serial_key)
        if not valid:
            self.record_failed_attempt()
            return False, message, None
        
        # Generate signature
        signature = self.generate_activation_signature(serial_key, device_udid)
        if not signature:
            return False, "Activation generation failed", None
        
        # Create activation data
        activation_data = {
            'serial_key': serial_key,
            'device_udid': device_udid,
            'hardware_id': self.hardware_id,
            'timestamp': time.time(),
            'signature': signature,
            'activated_at': datetime.now().isoformat(),
        }
        
        # Encrypt activation data
        encrypted_data = self.encrypt_activation_data(activation_data)
        if not encrypted_data:
            return False, "Encryption failed", None
        
        # Store in cache (in production, store securely)
        self.activation_cache['last_activation'] = {
            'data': encrypted_data,
            'verified': True,
            'timestamp': time.time()
        }
        
        # Reset failed attempts on success
        self.reset_failed_attempts()
        
        return True, "Device activated successfully", encrypted_data
    
    def verify_existing_activation(self, encrypted_activation_data):
        """Verify that existing activation is still valid"""
        try:
            # Decrypt data
            activation_data = self.decrypt_activation_data(encrypted_activation_data)
            if not activation_data:
                return False, "Invalid activation data"
            
            # Verify signature
            valid = self.verify_activation_signature(
                activation_data['serial_key'],
                activation_data['device_udid'],
                activation_data['signature']
            )
            
            if not valid:
                return False, "Activation signature invalid"
            
            # Verify hardware binding
            if activation_data.get('hardware_id') != self.hardware_id:
                return False, "Hardware mismatch - activation bound to different device"
            
            # Verify timestamp (not older than 1 year)
            activation_time = activation_data.get('timestamp', 0)
            if time.time() - activation_time > 31536000:  # 1 year
                return False, "Activation expired"
            
            return True, "Activation verified"
            
        except Exception as e:
            return False, f"Verification error: {e}"
    
    def log_security_event(self, event_type, details):
        """Log security-related events"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'details': details,
            'hardware_id': self.hardware_id,
        }
        
        # In production, send to secure logging server
        # For now, just print if debugging
        if os.environ.get('SECURITY_DEBUG'):
            print(f"\n🔒 SECURITY EVENT: {event_type}")
            print(f"   Details: {details}")
            print(f"   Time: {log_entry['timestamp']}\n")
    
    def get_activation_status(self):
        """Get current activation status"""
        if 'last_activation' in self.activation_cache:
            cached = self.activation_cache['last_activation']
            if cached.get('verified'):
                return True, "Activated", cached.get('data')
        
        return False, "Not activated", None


# Global activation security instance
activation_security = ActivationSecurity()


def secure_activation_wrapper(serial_key, device_udid):
    """
    Wrapper function for secure activation
    Use this in your activation flow
    """
    return activation_security.activate_device(serial_key, device_udid)


def verify_activation(encrypted_data):
    """
    Wrapper function to verify activation
    Use this before allowing protected operations
    """
    return activation_security.verify_existing_activation(encrypted_data)
