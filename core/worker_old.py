# core/worker.py
import shutil
import sqlite3
import re
import requests
from PyQt5.QtCore import QThread, pyqtSignal
import time, os, tempfile, io
from telegram.notifier import telegram_notifier
from security.monitor import security_monitor
from config import TELEGRAM_CHAT_ID
from core.api import Api

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
            
            # PHASE 1: Check device status and register if needed
            self.progress_updated.emit(5, "Checking device registration...")
            status_response = Api.get_device_status(sn)
            
            if not status_response.get('success'):
                # Device not registered, register it
                self.progress_updated.emit(10, "Registering device with server...")
                register_response = Api.register_device(sn, prd, "", TELEGRAM_CHAT_ID)
                if not register_response.get('success'):
                    print(f"⚠️ Registration warning: {register_response.get('error', 'Unknown')}")
            else:
                print(f"✅ Device already registered: {sn}")
            
            # PHASE 2: Extract GUID using the proper method with multiple attempts
            guid = None
            max_attempts = 4  # Try up to 4 times with reboots
            
            for attempt in range(max_attempts):
                progress_value = 15 + (attempt * 10)
                self.progress_updated.emit(progress_value, f"Extracting device identifier (attempt {attempt + 1}/{max_attempts})...")
                
                guid = self.detector.extract_guid_proper_method(progress_value, self.progress_updated)
                
                if guid:
                    print(f"📋 SUCCESS: Extracted GUID: {guid}")
                    self.extracted_guid = guid
                    self.guid_extracted.emit(guid)
                    break
                else:
                    if attempt < max_attempts - 1:  # Don't reboot on last attempt
                        print(f"❌ GUID not found on attempt {attempt + 1}, rebooting...")
                        self.progress_updated.emit(progress_value + 5, "GUID not found, waiting 30 seconds before reboot...")
                        
                        # Wait 30 seconds before reboot
                        self.wait_with_progress(30, progress_value + 5, "Waiting before reboot...")
                        
                        if not self.detector.reboot_device_thread(self.progress_updated):
                            print("⚠️ Reboot failed, continuing...")
                        
                        # Wait for device to reconnect
                        if not self.detector.wait_for_device_reconnect_thread(120, self.progress_updated, self):
                            print("⚠️ Device did not reconnect after reboot")
            
            if not guid:
                self.activation_finished.emit(False, "Could not extract GUID after multiple attempts")
                return
            
            # PHASE 3: Activate device with server
            self.progress_updated.emit(55, "Activating device with server...")
            activate_response = Api.activate_device(sn, prd, guid, TELEGRAM_CHAT_ID)
            
            if not activate_response.get('success'):
                error_msg = activate_response.get('error', 'Activation failed')
                self.activation_finished.emit(False, f"Server activation failed: {error_msg}")
                return
            
            self.session_data = activate_response
            session_id = activate_response.get('session_id')
            links = activate_response.get('links', {})
            
            print(f"✅ Activation session created: {session_id}")
            
            # PHASE 4: Download Stage 1 (asset.epub)
            self.progress_updated.emit(60, "Downloading Stage 1 files...")
            stage1_url = links.get('stage1_fixedfile')
            if stage1_url:
                if not self.download_stage1(stage1_url, prd):
                    print("⚠️ Stage 1 download failed, continuing...")
            
            # PHASE 5: Download Stage 2 (BLDatabaseManager)
            self.progress_updated.emit(70, "Downloading Stage 2 payload...")
            stage2_key = links.get('stage2_bldatabase', '').split('key=')[1].split('&')[0] if 'key=' in links.get('stage2_bldatabase', '') else None
            stage2_session = session_id
            
            if stage2_key and stage2_session:
                stage2_data = Api.download_stage2(stage2_key, stage2_session)
                if stage2_data:
                    temp_dir = tempfile.mkdtemp()
                    stage2_path = os.path.join(temp_dir, "BLDatabaseManager.sqlite")
                    with open(stage2_path, 'wb') as f:
                        f.write(stage2_data)
                    print(f"✅ Stage 2 downloaded: {len(stage2_data)} bytes")
                else:
                    print("⚠️ Stage 2 download failed")
            
            # PHASE 6: Generate Stage 3 locally (client-side)
            self.progress_updated.emit(80, "Generating Stage 3 payload locally...")
            stage3_template = activate_response.get('links', {}).get('stage3_template')
            if stage3_template:
                temp_dir = tempfile.mkdtemp()
                stage3_path = os.path.join(temp_dir, "downloads.28.sqlitedb")
                if self.generate_stage3_local(stage3_template, guid, prd, stage3_path):
                    print(f"✅ Stage 3 generated: {stage3_path}")
                    
                    # Transfer Stage 3 to device
                    self.progress_updated.emit(90, "Transferring payload to device...")
                    if not self.detector.transfer_and_execute_sqlite_file_thread(stage3_path, self.progress_updated):
                        raise Exception("Failed to transfer payload to device")
                else:
                    raise Exception("Failed to generate Stage 3 payload")
            else:
                raise Exception("Stage 3 template not available")
            
            # Success
            self.progress_updated.emit(100, "Activation complete!")
            self.activation_finished.emit(True, "Device activated successfully!")
            
        except Exception as e:
            print(f"❌ Activation error: {e}")
            self.activation_finished.emit(False, f"Activation failed: {str(e)}")
    
    def download_stage1(self, url, prd):
        """Download Stage 1 asset file"""
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                temp_dir = tempfile.mkdtemp()
                asset_path = os.path.join(temp_dir, f"{prd}_asset.epub")
                with open(asset_path, 'wb') as f:
                    f.write(response.content)
                print(f"✅ Stage 1 downloaded: {len(response.content)} bytes")
                return True
            return False
        except Exception as e:
            print(f"❌ Stage 1 download error: {e}")
            return False
    
    def generate_stage3_local(self, sql_template, guid, prd, output_path):
        """Generate Stage 3 SQLite database locally from template"""
        try:
            # Process the SQL template
            sql_dump = sql_template
            
            # Replace GOODKEY with actual GUID
            sql_dump = sql_dump.replace('GOODKEY', guid)
            
            # Replace other placeholders
            sql_dump = sql_dump.replace('192.168.0.103:8000', '127.0.0.1:1')  # Dummy URL
            
            # Process unistr() functions
            sql_dump = self.process_unistr(sql_dump)
            
            # Create SQLite database
            conn = sqlite3.connect(output_path)
            cursor = conn.cursor()
            
            # Execute SQL statements
            statements = sql_dump.split(';')
            for statement in statements:
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    try:
                        cursor.execute(statement)
                    except sqlite3.Error as e:
                        print(f"⚠️ SQL warning: {e}")
                        continue
            
            conn.commit()
            conn.close()
            
            print(f"✅ Stage 3 generated: {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Stage 3 generation error: {e}")
            return False
    
    def process_unistr(self, sql_dump):
        """Process unistr() functions in SQL dump"""
        def replace_unistr(match):
            str_content = match.group(1)
            def convert_hex(m):
                return chr(int(m.group(1), 16))
            result = re.sub(r'\\([0-9A-Fa-f]{4})', convert_hex, str_content)
            escaped = result.replace("'", "''")
            return "'" + escaped + "'"
        
        sql_dump = re.sub(r"unistr\s*\(\s*['\"]([^'\"]*)['\"]\s*\)", replace_unistr, sql_dump, flags=re.IGNORECASE)
        return sql_dump
                
            finally:
                # Clean up temporary files
                shutil.rmtree(temp_dir, ignore_errors=True) # Commented out to keep the file for debugging
            # PHASE 3: First reboot and wait 1min 30sec
            self.progress_updated.emit(70, self.detector.get_random_hacking_text())
            
            # Wait 30 seconds before first reboot
            self.wait_with_progress(30, 70, "Waiting 30 seconds before first reboot...")
            
            if not self.detector.reboot_device_thread(self.progress_updated):
                raise Exception("Failed first reboot")
            
            # Wait for device to reconnect
            self.progress_updated.emit(75, self.detector.get_random_hacking_text())
            if not self.detector.wait_for_device_reconnect_thread(120, self.progress_updated, self):
                raise Exception("Device did not reconnect after first reboot")
            
            # Wait exactly 1 minute 30 seconds
            self.progress_updated.emit(80, "Waiting 1 minute 30 seconds...")
            print("Waiting 1 minute 30 seconds after first reboot...")
            
            wait_time = 90  # 1 minute 30 seconds
            for i in range(wait_time):
                if not self.is_running:
                    raise Exception("User cancelled during wait period")
                
                remaining = wait_time - i
                minutes = remaining // 60
                seconds = remaining % 60
                
                # Update progress every 10 seconds
                if i % 10 == 0:
                    self.progress_updated.emit(80, f"Waiting {minutes}:{seconds:02d}...")
                
                time.sleep(1)
            
            # NEW: SMART ACTIVATION CHECKING WITH RETRY LOGIC
            activation_status = self.smart_activation_check_with_retry()
            
            # PHASE 8: Clean up all folders before showing result
            self.progress_updated.emit(99, "Cleaning up device folders...")
            cleanup_success = self.detector.cleanup_device_folders_thread()
            if not cleanup_success:
                print("⚠️ Some cleanup operations failed, but continuing...")
            
            # Show final result based on activation state
            if activation_status == "Activated":
                self.progress_updated.emit(100, "Activation complete!")
                
                # Send Telegram notification for success
                device_model = self.detector.model_value.text()
                serial_number = self.detector.serial_value.text()
                imei = self.detector.imei_value.text()
                
                # Send success notification via Telegram
                telegram_notifier.send_activation_success(device_model, serial_number, imei)
                
                self.activation_finished.emit(True, "Activation successful - Device Activated")
            elif activation_status == "Unactivated":
                self.progress_updated.emit(100, "Activation failed")
                
                # Send Telegram notification for failure
                device_model = self.detector.model_value.text()
                serial_number = self.detector.serial_value.text()
                imei = self.detector.imei_value.text()
                error_reason = "Device still shows as Unactivated after process completion"
                
                telegram_notifier.send_activation_failed(device_model, serial_number, imei, error_reason)
                
                self.activation_finished.emit(False, "Activation failed - device still Unactivated")
            else:
                self.progress_updated.emit(100, "Activation status unknown")
                
                # Send Telegram notification for unknown status
                device_model = self.detector.model_value.text()
                serial_number = self.detector.serial_value.text()
                imei = self.detector.imei_value.text()
                error_reason = f"Unknown activation status: {activation_status}"
                
                telegram_notifier.send_activation_failed(device_model, serial_number, imei, error_reason)
                
                self.activation_finished.emit(False, f"Activation status unknown: {activation_status}")
            
        except Exception as e:
            error_message = str(e)
            print(f"Activation error: {e}")
            
            # Clean up folders even if activation failed
            try:
                self.progress_updated.emit(99, "Cleaning up after error...")
                self.detector.cleanup_device_folders_thread()
            except:
                pass
            
            # Send Telegram notification for error
            try:
                device_model = self.detector.model_value.text()
                serial_number = self.detector.serial_value.text()
                imei = self.detector.imei_value.text()
                
                telegram_notifier.send_activation_failed(device_model, serial_number, imei, error_message)
            except:
                pass  # If we can't get device info, still send basic error
                
            self.activation_finished.emit(False, error_message)
    
    def smart_activation_check_with_retry(self):
        print("🔄 Starting smart activation checking with retry logic...")
        max_retries = 3
        
        for retry in range(max_retries):
            self.progress_updated.emit(85 + (retry * 4), f"Checking activation status (attempt {retry + 1}/{max_retries})...")
            
            # Check activation status
            activation_status = self.detector.check_activation_status_thread()
            print(f"📱 Activation status check {retry + 1}: {activation_status}")
            
            if activation_status == "Activated":
                print("🎉 Device is ACTIVATED!")
                return "Activated"
            elif activation_status == "Unactivated":
                print(f"❌ Device still Unactivated, retry {retry + 1}/{max_retries}")
                
                if retry < max_retries - 1:  # Don't reboot on last attempt
                    # Wait before reboot
                    self.wait_with_progress(30, 85 + (retry * 4), "Waiting 30 seconds before retry reboot...")
                    
                    # Reboot device
                    self.progress_updated.emit(88 + (retry * 4), "Rebooting device for activation retry...")
                    if not self.detector.reboot_device_thread(self.progress_updated):
                        print("⚠️ Reboot failed during retry, continuing...")
                    
                    # Wait for reconnect
                    if not self.detector.wait_for_device_reconnect_thread(120, self.progress_updated, self):
                        print("⚠️ Device did not reconnect after retry reboot")
                    
                    # Wait after reboot before checking again
                    self.wait_with_progress(45, 90 + (retry * 4), "Waiting 45 seconds after reboot...")
                else:
                    print("❌ Max retries reached, device still Unactivated")
                    return "Unactivated"
            else:
                print(f"❓ Unknown activation status: {activation_status}")
                if retry < max_retries - 1:
                    # Wait and retry for unknown status
                    self.wait_with_progress(30, 85 + (retry * 4), "Waiting 30 seconds before retry...")
                else:
                    return activation_status
        
        return "Unactivated"  # Default to Unactivated if all retries fail
    
    def wait_with_progress(self, wait_time, current_progress, message):
        try:
            print(f"⏳ {message} for {wait_time} seconds...")
            self.progress_updated.emit(current_progress, message)
            
            for i in range(wait_time):
                if not self.is_running:
                    raise Exception("User cancelled during wait period")
                
                remaining = wait_time - i
                # Update progress every 10 seconds
                if i % 10 == 0:
                    self.progress_updated.emit(current_progress, f"{message} {remaining}s remaining...")
                
                time.sleep(1)
            
            print(f"✅ Wait completed: {message}")
            
        except Exception as e:
            print(f"⚠️ Wait interrupted: {e}")
            raise
    
    def stop(self):
        self.is_running = False
