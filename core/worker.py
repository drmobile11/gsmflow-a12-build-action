# core/worker.py
import shutil
from PyQt5.QtCore import QThread, pyqtSignal
import time
import os
import tempfile
from security.monitor import security_monitor
from core.api import Api
import config

# Production logging helper
def log_message(message, level="info"):
    """Log message only if technical logs are enabled"""
    if config.SHOW_TECHNICAL_LOGS:
        print(message)

class ActivationWorker(QThread):
    progress_updated = pyqtSignal(int, str)
    activation_finished = pyqtSignal(bool, str)
    guid_extracted = pyqtSignal(str)
    
    def __init__(self, detector):
        super().__init__()
        self.detector = detector
        self.is_running = True
        self.extracted_guid = None
        self.session_data = None
        
    def run(self):
        temp_dir = None
        try:
            # Security check at start
            if security_monitor.check_api_sniffing() or security_monitor.check_proxy_usage():
                self.activation_finished.emit(False, "Security violation detected - Proxy usage not allowed")
                return
            
            # Get device info
            sn = self.detector.current_serial
            prd = self.detector.current_product_type
            
            if not sn or not prd:
                self.activation_finished.emit(False, "Device information not available")
                return
            
            # PHASE 1: Register device with server
            self.progress_updated.emit(5, "Connecting to server...")
            try:
                register_response = Api.register_device(sn, prd)
                if register_response.get('success'):
                    log_message(f"✅ Device registered: {sn}")
                else:
                    log_message(f"⚠️ Registration warning: {register_response.get('error', 'Unknown')}")
            except Exception as e:
                log_message(f"⚠️ Server connection failed: {e}")
                self.activation_finished.emit(False, "Cannot connect to server. Please ensure server is running.")
                return
            
            # PHASE 2: Extract device GUID
            guid = None
            max_attempts = 4
            
            for attempt in range(max_attempts):
                progress_value = 15 + (attempt * 10)
                self.progress_updated.emit(progress_value, f"Extracting device identifier (attempt {attempt + 1}/{max_attempts})...")
                
                guid = self.detector.extract_guid_proper_method(progress_value, self.progress_updated)
                
                if guid:
                    log_message(f"✅ GUID extracted: {guid}")
                    self.extracted_guid = guid
                    self.guid_extracted.emit(guid)
                    break
                else:
                    if attempt < max_attempts - 1:
                        log_message(f"⚠️ GUID not found, retrying...")
                        self.progress_updated.emit(progress_value + 5, "Preparing device...")
                        
                        self.wait_with_progress(30, progress_value + 5, "Waiting...")
                        
                        if not self.detector.reboot_device_thread(self.progress_updated):
                            log_message("⚠️ Reboot failed")
                        
                        if not self.detector.wait_for_device_reconnect_thread(120, self.progress_updated, self):
                            log_message("⚠️ Reconnection timeout")
            
            if not guid:
                self.activation_finished.emit(False, "Could not extract device identifier. Please try again.")
                return
            
            # Create temporary directory
            temp_dir = tempfile.mkdtemp()
            local_file_path = os.path.join(temp_dir, "downloads.28.sqlitedb")
            
            # PHASE 3: Request activation from server
            self.progress_updated.emit(50, "Requesting activation...")
            
            try:
                log_message(f"� Requesting activation for {sn}")
                activate_response = Api.activate_device(sn, prd, guid)
                
                if not activate_response.get('success'):
                    error_msg = activate_response.get('error', 'Unknown error')
                    log_message(f"❌ Server error: {error_msg}")
                    
                    # Check for specific error types
                    if 'banned' in error_msg.lower():
                        self.activation_finished.emit(False, "Device is banned. Contact support.")
                    elif 'pending' in error_msg.lower():
                        self.activation_finished.emit(False, "Device pending admin approval. Please wait.")
                    elif 'not registered' in error_msg.lower():
                        self.activation_finished.emit(False, "Device not registered. Please register first.")
                    else:
                        self.activation_finished.emit(False, f"Server error: {error_msg}")
                    return
                
                log_message("✅ Activation response received")
                
                # Get session and URLs
                session_id = activate_response.get('session_id')
                links = activate_response.get('links', {})
                stage3_url = links.get('stage3_final')
                
                if not stage3_url:
                    log_message("❌ Server did not provide Stage 3 URL")
                    self.activation_finished.emit(False, "Server error: Missing activation data")
                    return
                
                log_message(f"🎫 Session: {session_id}")
                log_message(f"📥 Stage 3 URL: {stage3_url}")
                
                # Download Stage 3 from server
                self.progress_updated.emit(55, "Downloading activation data...")
                stage3_data = Api.download_file(stage3_url)
                
                if not stage3_data:
                    log_message("❌ Failed to download Stage 3")
                    self.activation_finished.emit(False, "Failed to download activation data")
                    return
                
                # Save Stage 3 to temp file
                with open(local_file_path, 'wb') as f:
                    f.write(stage3_data)
                
                log_message(f"✅ Stage 3 downloaded: {len(stage3_data)} bytes")
                
            except Exception as e:
                log_message(f"❌ Activation request failed: {e}")
                self.activation_finished.emit(False, "Server unavailable. Please ensure server is running.")
                return
            
            # PHASE 4: Prepare device
            self.progress_updated.emit(60, "Preparing device...")
            log_message("🧹 Preparing device folders...")
            self.detector.clean_downloads_files()
            
            # PHASE 5: Upload activation data
            self.progress_updated.emit(65, "Uploading activation data...")
            log_message(f"📤 Uploading activation files...")
            
            if not self.detector.transfer_file_to_device(local_file_path, 'Downloads/downloads.28.sqlitedb'):
                raise Exception("Failed to upload activation data")
            
            log_message("✅ Upload successful")
            
            # PHASE 6: First device restart
            self.progress_updated.emit(70, "Restarting device (1/3)...")
            log_message("🔄 Restarting device...")
            
            if not self.detector.reboot_device_thread(self.progress_updated):
                raise Exception("Device restart failed")
            
            # Wait for device to reconnect
            self.progress_updated.emit(72, "Waiting for device...")
            if not self.detector.wait_for_device_reconnect_thread(120, self.progress_updated, self):
                raise Exception("Device did not reconnect")
            
            log_message("✅ Device reconnected")
            
            # PHASE 7: Verify first stage
            self.progress_updated.emit(75, "Verifying activation (1/3)...")
            log_message("🔍 Verifying activation progress...")
            
            max_stage1_attempts = 3
            stage1_success = False
            
            for attempt in range(1, max_stage1_attempts + 1):
                log_message(f"  Verification attempt {attempt}/{max_stage1_attempts}")
                
                # Wait for processing
                time.sleep(10)
                
                if self.detector.verify_stage1_files():
                    stage1_success = True
                    break
                else:
                    if attempt < max_stage1_attempts:
                        log_message(f"  ⚠️ Not ready, retrying...")
                        # Re-upload and reboot
                        self.detector.clean_downloads_files()
                        self.detector.transfer_file_to_device(local_file_path, 'Downloads/downloads.28.sqlitedb')
                        self.detector.reboot_device_thread(self.progress_updated)
                        self.detector.wait_for_device_reconnect_thread(120, self.progress_updated, self)
            
            if not stage1_success:
                raise Exception("Activation verification failed")
            
            log_message("✅ First stage verified")
            
            # PHASE 8: Wait for system processing
            self.progress_updated.emit(78, "Processing activation (2/3)...")
            log_message("⏳ Waiting for system processing...")
            
            if not self.detector.verify_itunes_metadata(timeout=120):
                raise Exception("System processing timeout")
            
            log_message("✅ Processing complete")
            
            # PHASE 9: Prepare second stage
            self.progress_updated.emit(80, "Preparing next stage...")
            log_message("📋 Preparing second stage...")
            
            if not self.detector.copy_itunes_to_books():
                log_message("⚠️ Stage preparation warning, continuing...")
            else:
                log_message("✅ Second stage prepared")
            
            # PHASE 10: Second device restart
            self.progress_updated.emit(82, "Restarting device (2/3)...")
            log_message("🔄 Second restart...")
            
            if not self.detector.reboot_device_thread(self.progress_updated):
                raise Exception("Device restart failed")
            
            # Wait for device to reconnect
            if not self.detector.wait_for_device_reconnect_thread(120, self.progress_updated, self):
                raise Exception("Device did not reconnect")
            
            log_message("✅ Device reconnected")
            
            # PHASE 11: Verify second stage
            self.progress_updated.emit(85, "Verifying activation (2/3)...")
            log_message("🔍 Verifying second stage...")
            
            # Wait for processing
            time.sleep(15)
            
            # PHASE 12: Final device restart
            self.progress_updated.emit(88, "Restarting device (3/3)...")
            log_message("🔄 Final restart...")
            
            if not self.detector.reboot_device_thread(self.progress_updated):
                log_message("⚠️ Final restart warning, continuing...")
            
            # Wait for device to reconnect
            if not self.detector.wait_for_device_reconnect_thread(120, self.progress_updated, self):
                log_message("⚠️ Reconnection timeout, continuing...")
            
            # PHASE 13: Check activation status
            self.progress_updated.emit(90, "Checking activation status...")
            log_message("🔍 Checking activation status...")
            
            # Smart activation checking with retry
            activation_status = self.smart_activation_check_with_retry()
            
            # PHASE 14: Clean up device
            self.progress_updated.emit(99, "Finalizing...")
            cleanup_success = self.detector.cleanup_device_folders_thread()
            if not cleanup_success:
                log_message("⚠️ Cleanup warning")
            
            # Show final result
            if activation_status == "Activated":
                self.progress_updated.emit(100, "Activation complete!")
                log_message("🎉 Activation successful!")
                self.activation_finished.emit(True, "Device activated successfully")
            elif activation_status == "Unactivated":
                self.progress_updated.emit(100, "Activation incomplete")
                log_message("❌ Activation incomplete")
                self.activation_finished.emit(False, "Activation incomplete. Please try again.")
            else:
                self.progress_updated.emit(100, "Activation status unknown")
                log_message(f"❓ Unknown status: {activation_status}")
                self.activation_finished.emit(False, "Status unknown. Please contact support.")
            
        except Exception as e:
            error_message = str(e)
            log_message(f"❌ Activation error: {e}")
            
            # Clean up folders even if activation failed
            try:
                self.progress_updated.emit(99, "Cleaning up...")
                self.detector.cleanup_device_folders_thread()
            except:
                pass
            
            # Show user-friendly error message
            user_message = "Activation failed. Please try again or contact support."
            if "timeout" in error_message.lower():
                user_message = "Connection timeout. Please check your connection and try again."
            elif "server" in error_message.lower() or "unavailable" in error_message.lower():
                user_message = "Server unavailable. Please ensure server is running."
            elif "device" in error_message.lower() and "disconnect" in error_message.lower():
                user_message = "Device disconnected. Please reconnect and try again."
            
            self.activation_finished.emit(False, user_message)
        
        finally:
            # Clean up temporary files
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except:
                    pass
    
    def smart_activation_check_with_retry(self):
        """Check activation status with retry logic"""
        log_message("🔄 Checking activation status with retry...")
        max_retries = 3
        
        for retry in range(max_retries):
            self.progress_updated.emit(85 + (retry * 4), f"Verifying activation (attempt {retry + 1}/{max_retries})...")
            
            # Check activation status
            activation_status = self.detector.check_activation_status_thread()
            log_message(f"📱 Status check {retry + 1}: {activation_status}")
            
            if activation_status == "Activated":
                log_message("🎉 Device is activated!")
                return "Activated"
            elif activation_status == "Unactivated":
                log_message(f"❌ Not activated yet, retry {retry + 1}/{max_retries}")
                
                if retry < max_retries - 1:
                    # Wait before retry
                    self.wait_with_progress(30, 85 + (retry * 4), "Waiting before retry...")
                    
                    # Reboot device
                    self.progress_updated.emit(88 + (retry * 4), "Restarting device for retry...")
                    if not self.detector.reboot_device_thread(self.progress_updated):
                        log_message("⚠️ Restart failed, continuing...")
                    
                    # Wait for reconnect
                    if not self.detector.wait_for_device_reconnect_thread(120, self.progress_updated, self):
                        log_message("⚠️ Device reconnection timeout")
                    
                    # Wait after reboot
                    self.wait_with_progress(45, 90 + (retry * 4), "Processing...")
                else:
                    log_message("❌ Max retries reached")
                    return "Unactivated"
            else:
                log_message(f"❓ Unknown status: {activation_status}")
                if retry < max_retries - 1:
                    self.wait_with_progress(30, 85 + (retry * 4), "Waiting before retry...")
                else:
                    return activation_status
        
        return "Unactivated"
    
    def wait_with_progress(self, wait_time, current_progress, message):
        """Wait with progress updates"""
        try:
            log_message(f"⏳ {message} ({wait_time}s)...")
            self.progress_updated.emit(current_progress, message)
            
            for i in range(wait_time):
                if not self.is_running:
                    raise Exception("Operation cancelled")
                
                remaining = wait_time - i
                # Update progress every 10 seconds
                if i % 10 == 0:
                    self.progress_updated.emit(current_progress, f"{message} {remaining}s...")
                
                time.sleep(1)
            
            log_message(f"✅ Wait completed")
            
        except Exception as e:
            log_message(f"⚠️ Wait interrupted: {e}")
            raise
    
    def stop(self):
        """Stop the worker"""
        self.is_running = False
