# core/detector.py
import sys
import os
import subprocess
import time
import random
from urllib.parse import quote
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QTimer, pyqtSignal, Qt, pyqtSlot
from PyQt5.QtGui import QPalette, QColor, QClipboard
from PyQt5.QtWidgets import QApplication, QVBoxLayout

# Import QColor for theme
from PyQt5.QtGui import QColor as QtColor
import threading, time, os, requests, re, webbrowser, tempfile, shutil
from core.worker import ActivationWorker
from gui.dialogs import CustomMessageBox, ActivationResultDialog
from security.monitor import security_monitor
from utils.helpers import run_subprocess_no_console, get_lib_path
from PyQt5 import uic
from core.api import Api
import config

# Get base directory for PyInstaller and Nuitka bundle support
def get_base_dir():
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller - use _MEIPASS
            return sys._MEIPASS
        else:
            # Nuitka - use executable directory
            return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = get_base_dir()

# Production logging helper
def log_message(message, level="info"):
    """Log message only if technical logs are enabled"""
    if config.SHOW_TECHNICAL_LOGS:
        print(message)

class DeviceDetector(QMainWindow):
    device_connected = pyqtSignal(bool)
    model_received = pyqtSignal(str)
    show_auth_dialog = pyqtSignal(str, str)
    enable_activate_btn = pyqtSignal(bool)
    update_status_label = pyqtSignal(str, str)
    update_progress = pyqtSignal(int, str)
    
    # Vercel Dark Theme Colors (darker)
    BG_DARK = "#000000"          # Pure black background
    BG_CARD = "#111111"          # Slightly lighter for cards
    BG_INPUT = "#1a1a1a"         # Input fields
    BORDER = "#333333"           # Subtle borders
    TEXT_PRIMARY = "#ffffff"     # White text
    TEXT_SECONDARY = "#888888"   # Gray secondary text
    ACCENT = "#ffffff"           # White accent
    SUCCESS = "#00ff88"          # Bright green
    WARNING = "#ffaa00"          # Orange
    DANGER = "#ff4444"           # Red
    def __init__(self):
        super().__init__()
        
        # Load UI from correct path (handles PyInstaller bundle)
        ui_path = os.path.join(BASE_DIR, "mainUI.ui")
        uic.loadUi(ui_path, self)
        
        # Apply dark theme from Qt Designer (defined in mainUI.ui)
        # No need to apply programmatically - it's in the .ui file
        
        self.device_info = {}
        self.current_serial = None
        self.current_product_type = None
        self.cached_models = {} 
        self.authorization_checked = False
        self.device_authorized = False
        self.activation_in_progress = False
        self.zrac_guid_data = None
        self.extracted_guid = None
        self.activation_worker = None
        
        # Setup development mode
        self.setup_dev_mode()
        
        # Setup click-to-copy for device info labels
        self.setup_click_to_copy()
        
        # Start security monitoring in background
        self.start_security_monitoring()
        
        # Connect signals
        self.device_connected.connect(self.on_device_connected)
        self.model_received.connect(self.on_model_received)
        self.show_auth_dialog.connect(self.on_show_auth_dialog)
        self.update_status_label.connect(self.on_update_status_label)
        self.update_progress.connect(self.on_update_progress)
        self.enable_activate_btn.connect(self.set_activate_button_state)
        self.activate_btn.clicked.connect(self.on_activate_button_clicked)
        
        # Create refresh button
        self.setup_refresh_button()
        
        # Setup periodic authorization refresh (every 10 seconds when not authorized)
        self.auth_refresh_timer = QTimer()
        self.auth_refresh_timer.timeout.connect(self._refresh_authorization)
        self.auth_refresh_timer.start(10000)  # 10 seconds
        
        self.setup_device_monitor()
    
    def start_security_monitoring(self):
        def monitor():
            security_monitor.continuous_monitoring()
        
        security_thread = threading.Thread(target=monitor, daemon=True)
        security_thread.start()

        self.activate_btn.setProperty("state", "waiting")
        self.activate_btn.setCursor(Qt.ArrowCursor)
    
    def setup_dev_mode(self):
        """Development mode disabled in production"""
        pass
    
    def get_manual_guid(self):
        """Manual GUID disabled in production"""
        return None
    
    def setup_click_to_copy(self):
        """Setup click-to-copy functionality for device info labels"""
        # List of value labels that should be clickable
        clickable_labels = [
            self.model_value,
            self.serial_value,
            self.ios_value,
            self.imei_value
        ]
        
        for label in clickable_labels:
            # Make label selectable and clickable
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label.setCursor(Qt.PointingHandCursor)
            
            # Install event filter for click detection
            label.installEventFilter(self)
            
            # Add hover effect
            label.setStyleSheet(label.styleSheet() + """
                QLabel:hover {
                    background-color: #1f1f1f;
                    border-radius: 4px;
                    padding: 2px 4px;
                }
            """)
    
    def eventFilter(self, obj, event):
        """Handle click events on device info labels"""
        # Check if it's a mouse press on one of our clickable labels
        if event.type() == event.MouseButtonPress:
            clickable_labels = [
                self.model_value,
                self.serial_value,
                self.ios_value,
                self.imei_value
            ]
            
            if obj in clickable_labels:
                text = obj.text()
                # Only copy if it's not a placeholder
                if text and text not in ["—", "N/A", "Unknown", "Loading..."]:
                    clipboard = QApplication.clipboard()
                    clipboard.setText(text)
                    
                    # Show temporary feedback
                    original_text = obj.text()
                    original_style = obj.styleSheet()
                    
                    obj.setText("✓ Copied!")
                    obj.setStyleSheet(original_style + "color: #10b981; font-weight: bold;")
                    
                    # Reset after 1 second
                    QTimer.singleShot(1000, lambda: self.reset_label(obj, original_text, original_style))
                    
                    self.log(f"Copied to clipboard: {text}", "success")
                    return True
        
        # Pass event to parent
        return super().eventFilter(obj, event)
    
    def reset_label(self, label, original_text, original_style):
        """Reset label to original state after copy feedback"""
        label.setText(original_text)
        label.setStyleSheet(original_style)

    def force_dark_theme_on_all(self):
        """Force dark theme on all widgets after UI load"""
        dark_style = f"""
            QWidget {{
                background-color: {self.BG_DARK};
                color: {self.TEXT_PRIMARY};
            }}
            QLabel {{
                background-color: transparent;
                color: {self.TEXT_PRIMARY};
            }}
            QLineEdit {{
                background-color: {self.BG_INPUT};
                color: {self.TEXT_PRIMARY};
                border: 1px solid {self.BORDER};
                padding: 8px;
            }}
            QTextEdit {{
                background-color: {self.BG_INPUT};
                color: {self.TEXT_PRIMARY};
                border: 1px solid {self.BORDER};
            }}
            QPushButton {{
                background-color: {self.TEXT_PRIMARY};
                color: {self.BG_DARK};
                border: none;
                padding: 8px 16px;
            }}
            QFrame {{
                background-color: {self.BG_CARD};
                border: 1px solid {self.BORDER};
            }}
            QGroupBox {{
                background-color: {self.BG_CARD};
                border: 1px solid {self.BORDER};
                color: {self.TEXT_PRIMARY};
            }}
        """
        
        # Apply to self and all children
        self.setStyleSheet(dark_style)
        
        # Force update all widgets
        for widget in self.findChildren(QWidget):
            widget.setStyleSheet(dark_style)
            widget.update()
    
    def apply_dark_theme(self):
        """Apply Fusion dark theme matching main_GUI_windows.py"""
        # Set application-wide palette (exact copy from main_GUI_windows.py)
        app = QApplication.instance()
        if app:
            app.setStyle("Fusion")
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(35, 35, 35))
            palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            app.setPalette(palette)
        
        # Make device info labels selectable/copyable with context menu
        for label_name in ['model_value', 'serial_value', 'ios_value', 'imei_value', 'status_value']:
            if hasattr(self, label_name):
                label = getattr(self, label_name)
                label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
                label.setCursor(Qt.IBeamCursor)
                # Add context menu
                label.setContextMenuPolicy(Qt.CustomContextMenu)
                label.customContextMenuRequested.connect(lambda pos, lbl=label: self.show_label_context_menu(lbl, pos))
        
        # Log widget is now in mainUI.ui - show startup message
        self.log("RhaulH A12 Bypass Tool", "success")
        self.log("Ready to activate your device", "info")

    def show_label_context_menu(self, label, pos):
        """Show context menu for device info labels"""
        menu = QMenu(self)
        # Style is now applied globally
        
        copy_action = menu.addAction("📋 Copy")
        copy_all_action = menu.addAction("📋 Copy All Device Info")
        
        action = menu.exec_(label.mapToGlobal(pos))
        
        if action == copy_action:
            clipboard = QApplication.clipboard()
            clipboard.setText(label.text())
            self.log(f"Copied: {label.text()}", "success")
        elif action == copy_all_action:
            self.copy_all_device_info()

    def copy_all_device_info(self):
        """Copy all device information to clipboard"""
        info_lines = []
        
        labels = {
            'Model': 'model_value',
            'Serial': 'serial_value',
            'iOS Version': 'ios_value',
            'IMEI': 'imei_value',
            'Status': 'status_value'
        }
        
        for label_name, attr_name in labels.items():
            if hasattr(self, attr_name):
                value = getattr(self, attr_name).text()
                info_lines.append(f"{label_name}: {value}")
        
        info_text = "\n".join(info_lines)
        clipboard = QApplication.clipboard()
        clipboard.setText(info_text)
        
        self.log("All device info copied to clipboard", "success")

    def log(self, message: str, level: str = "info"):
        """Add log message - only shows in development mode"""
        if not hasattr(self, 'log_text'):
            return
        
        # Only show logs if technical logs are enabled
        if not config.SHOW_TECHNICAL_LOGS:
            # In production, only show important messages
            if level not in ['success', 'error', 'warn', 'warning']:
                return
        
        # Color mapping
        colors = {
            'success': '#4caf50',   # Green
            'error': '#f44336',     # Red
            'warn': '#ff9800',      # Orange
            'warning': '#ff9800',   # Orange
            'info': '#64b5f6',      # Light blue
            'step': '#2196f3',      # Blue
            'detail': '#90a4ae'     # Gray
        }
        
        color = colors.get(level, '#e0e0e0')
        timestamp = time.strftime("%H:%M:%S")
        
        html = f'<span style="color:#78909c;">[{timestamp}]</span> <span style="color:{color};">{message}</span><br>'
        
        self.log_text.append(html)
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @pyqtSlot(bool)
    def set_activate_button_state(self, enabled: bool):
        """Set activate button state with security validation"""
        # Check if device needs authorization (not registered or not authorized)
        needs_authorization = (
            self.current_serial is not None and
            self.current_product_type is not None and
            not self.device_authorized and
            self.authorization_checked
        )
        
        if needs_authorization:
            # Change button to "Request Authorization"
            self.activate_btn.setEnabled(True)
            self.activate_btn.setProperty("state", "request")
            self.activate_btn.setText("📨 Request Authorization")
            self.activate_btn.setCursor(Qt.PointingHandCursor)
            log_message("🔄 Button changed to 'Request Authorization'")
        elif enabled:
            # Check all required conditions for activation
            conditions_met = (
                self.current_serial is not None and
                self.current_product_type is not None and
                self.device_authorized and
                not self.activation_in_progress and
                self.authorization_checked
            )
            
            if conditions_met:
                self.activate_btn.setEnabled(True)
                self.activate_btn.setProperty("state", "ready")
                self.activate_btn.setText("🚀 Activate Device")
                self.activate_btn.setCursor(Qt.PointingHandCursor)
                log_message("✅ Activate button enabled - all conditions met")
            else:
                self.activate_btn.setEnabled(False)
                self.activate_btn.setProperty("state", "waiting")
                self.activate_btn.setText("⏳ Waiting for Authorization...")
                self.activate_btn.setCursor(Qt.ArrowCursor)
                log_message(f"⚠️ Activate button disabled - conditions not met")
        else:
            self.activate_btn.setEnabled(False)
            self.activate_btn.setProperty("state", "waiting")
            self.activate_btn.setText("⏳ Waiting for Authorization...")
            self.activate_btn.setCursor(Qt.ArrowCursor)

        self.activate_btn.style().unpolish(self.activate_btn)
        self.activate_btn.style().polish(self.activate_btn)
        self.activate_btn.update()

    # ========== CLEANUP METHODS ==========
    # ========== CLEANUP METHODS ==========
    
    def test_file_operations(self):
        """Test upload and delete operations on device"""
        try:
            print("\n🧪 Testing file operations on device...")
            
            # Create a test file locally
            import tempfile
            test_content = "This is a test file created by A12 Bypass Tool\nTimestamp: " + str(time.time())
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(test_content)
                local_test_file = f.name
            
            test_filename = "test_a12bypass.txt"
            device_path = f"Downloads/{test_filename}"
            
            # Test 1: Upload file
            print(f"📤 Test 1: Uploading {test_filename} to device...")
            success, output = self.afc_client_operation('put', local_test_file, device_path)
            
            if success:
                print(f"✅ Upload successful!")
            else:
                print(f"❌ Upload failed: {output}")
                os.unlink(local_test_file)
                return False
            
            # Test 2: Verify file exists
            print(f"🔍 Test 2: Verifying file exists on device...")
            success, output = self.afc_client_operation('ls', 'Downloads/')
            
            if success and test_filename in output:
                print(f"✅ File verified on device!")
            else:
                print(f"❌ File not found on device")
                os.unlink(local_test_file)
                return False
            
            # Test 3: Delete file
            print(f"🗑️ Test 3: Deleting file from device...")
            success, output = self.afc_client_operation('rm', device_path)
            
            if success:
                print(f"✅ Delete successful!")
            else:
                print(f"❌ Delete failed: {output}")
                os.unlink(local_test_file)
                return False
            
            # Test 4: Verify file is deleted
            print(f"🔍 Test 4: Verifying file is deleted...")
            success, output = self.afc_client_operation('ls', 'Downloads/')
            
            if success and test_filename not in output:
                print(f"✅ File successfully deleted from device!")
            else:
                print(f"⚠️ File may still exist on device")
            
            # Cleanup local file
            os.unlink(local_test_file)
            
            print("✅ All file operation tests passed!\n")
            return True
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            return False
    
    def cleanup_device_folders_thread(self):
        """Clean device folders - only delete specific bypass-related files"""
        try:
            print("🧹 Starting device folder cleanup...")
            
            deleted = 0
            
            # Clean Downloads folder
            deleted += self.clean_downloads_files()
            
            # Clean Books folder
            deleted += self.clean_books_files()
            
            # Clean iTunes_Control/iTunes folder
            deleted += self.clean_itunes_files()
            
            print(f"✅ Device folder cleanup completed - deleted {deleted} files")
            return True
            
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
            return False
    
    def clean_downloads_files(self):
        """Clean Downloads folder - only specific files"""
        try:
            success, output = self.afc_client_operation('ls', 'Downloads/')
            if not success:
                return 0
            
            files = [f.strip() for f in output.strip().split('\n') if f.strip()]
            deleted = 0
            
            # Target files for deletion
            target_files = ['downloads.28.sqlitedb', 'downloads.28.sqlitedb-shm', 'downloads.28.sqlitedb-wal']
            
            for filename in files:
                if filename in target_files or filename.startswith('test_'):
                    success, _ = self.afc_client_operation('rm', f'Downloads/{filename}')
                    if success:
                        print(f"  ✅ Deleted: Downloads/{filename}")
                        deleted += 1
            
            return deleted
        except Exception as e:
            print(f"❌ Error cleaning Downloads: {e}")
            return 0
    
    def clean_books_files(self):
        """Clean Books folder - only specific files"""
        try:
            success, output = self.afc_client_operation('ls', 'Books/')
            if not success:
                return 0
            
            files = [f.strip() for f in output.strip().split('\n') if f.strip()]
            deleted = 0
            
            # Target files for deletion
            target_files = ['iTunesMetadata.plist', 'asset.epub']
            
            for filename in files:
                if filename in target_files:
                    success, _ = self.afc_client_operation('rm', f'Books/{filename}')
                    if success:
                        print(f"  ✅ Deleted: Books/{filename}")
                        deleted += 1
            
            return deleted
        except Exception as e:
            print(f"❌ Error cleaning Books: {e}")
            return 0
    
    def clean_itunes_files(self):
        """Clean iTunes_Control/iTunes folder - only specific files"""
        try:
            success, output = self.afc_client_operation('ls', 'iTunes_Control/iTunes/')
            if not success:
                return 0
            
            files = [f.strip() for f in output.strip().split('\n') if f.strip()]
            deleted = 0
            
            # Target file for deletion
            if 'iTunesMetadata.plist' in files:
                success, _ = self.afc_client_operation('rm', 'iTunes_Control/iTunes/iTunesMetadata.plist')
                if success:
                    print(f"  ✅ Deleted: iTunes_Control/iTunes/iTunesMetadata.plist")
                    deleted += 1
            
            return deleted
        except Exception as e:
            print(f"❌ Error cleaning iTunes: {e}")
            return 0
    
    def verify_stage1_files(self):
        """Verify Stage 1 files exist after first reboot (downloads.28.sqlitedb + WAL/SHM)"""
        try:
            success, output = self.afc_client_operation('ls', 'Downloads/')
            if not success:
                return False
            
            files = output.strip().split('\n')
            has_db = 'downloads.28.sqlitedb' in files
            has_wal = 'downloads.28.sqlitedb-wal' in files
            has_shm = 'downloads.28.sqlitedb-shm' in files
            
            if has_db and (has_wal or has_shm):
                print(f"✅ Stage 1 verified: DB file + WAL/SHM files present")
                return True
            else:
                print(f"⚠️ Stage 1 incomplete: DB={has_db}, WAL={has_wal}, SHM={has_shm}")
                return False
                
        except Exception as e:
            print(f"❌ Error verifying Stage 1: {e}")
            return False
    
    def verify_itunes_metadata(self, timeout=60):
        """Wait for iTunesMetadata.plist to appear in iTunes_Control/iTunes"""
        try:
            print(f"⏳ Waiting for iTunesMetadata.plist (timeout: {timeout}s)...")
            
            import time
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                success, output = self.afc_client_operation('ls', 'iTunes_Control/iTunes/')
                if success and 'iTunesMetadata.plist' in output:
                    print(f"✅ iTunesMetadata.plist found in iTunes_Control/iTunes")
                    return True
                
                time.sleep(5)  # Check every 5 seconds
            
            print(f"❌ iTunesMetadata.plist not found after {timeout}s")
            return False
            
        except Exception as e:
            print(f"❌ Error verifying iTunes metadata: {e}")
            return False
    
    def copy_itunes_to_books(self):
        """Copy iTunesMetadata.plist from iTunes_Control/iTunes to Books"""
        try:
            print("📋 Copying iTunesMetadata.plist to Books folder...")
            
            source = 'iTunes_Control/iTunes/iTunesMetadata.plist'
            dest = 'Books/iTunesMetadata.plist'
            
            return self.copy_file_on_device(source, dest)
            
        except Exception as e:
            print(f"❌ Error copying file: {e}")
            return False
        
    def clean_folder(self, folder):
        """Legacy method - kept for compatibility"""
        try:
            success, output = self.afc_client_operation('ls', f'{folder}/')
            if not success:
                return False

            items = output.strip().split('\n')
            deleted_count = 0

            for item in items:
                item = item.strip()
                if not item or item in ['.', '..']:
                    continue

                full_path = f"{folder}/{item}"

                is_dir = False
                dir_check, dir_output = self.afc_client_operation('ls', f"{full_path}/")

                if dir_check:
                    is_dir = True

                if is_dir:
                    print(f"📁 Cleaning subfolder: {full_path}")
                    self.clean_folder(full_path)

                    # borrar la carpeta vacía
                    print(f"🗑️ Removing folder: {full_path}")
                    self.afc_client_operation('rmdir', full_path)
                else:
                    # 3. Es archivo → borrar
                    print(f"🗑️ Deleting file: {full_path}")
                    self.afc_client_operation('rm', full_path)

                deleted_count += 1

            print(f"✅ Cleaned {deleted_count} items in {folder}")
            return True

        except Exception as e:
            print(f"❌ Error cleaning {folder}: {e}")
            return False


    # ========== GUID EXTRACTION METHODS ==========
    
    def extract_guid_proper_method(self, progress_value, progress_signal):
        """Extract GUID using original activator method - NO REBOOT, just collect logs"""
        try:
            log_message("🔄 Starting GUID extraction process...")

            # Get device UDID
            progress_signal.emit(progress_value + 2, "Getting device information...")
            udid = self.get_device_udid()
            if not udid:
                log_message("❌ Cannot get device UDID")
                return None

            log_message(f"📋 Device UDID: {udid}")

            # NO REBOOT - Collect logs immediately (like original activator)
            progress_signal.emit(progress_value + 5, "Collecting device logs...")
            log_message("📝 Collecting device logs (this may take up to 2 minutes)...")

            log_archive_path = self.collect_syslog_with_pymobiledevice(udid)
            if not log_archive_path:
                log_message("❌ Failed to collect device logs")
                return None

            # Search for GUID in logs
            progress_signal.emit(progress_value + 10, "Searching for GUID...")
            log_message("🔍 Searching for SystemGroup GUID in logs...")

            guid = self.search_guid_in_logs_advanced(log_archive_path)

            # Clean up temporary files
            try:
                if os.path.exists(log_archive_path):
                    parent_dir = os.path.dirname(log_archive_path)
                    if os.path.exists(parent_dir):
                        shutil.rmtree(parent_dir, ignore_errors=True)
                        log_message("🧹 Cleaned up temporary log files")
            except Exception as e:
                log_message(f"⚠️ Cleanup warning: {e}")

            if guid:
                log_message(f"🎯 GUID extracted successfully: {guid}")
                return guid
            else:
                log_message("❌ Could not find GUID in logs")
                return None

        except Exception as e:
            log_message(f"❌ GUID extraction error: {e}")
            import traceback
            traceback.print_exc()
            return None


    def collect_syslog_with_pymobiledevice(self, udid):
        """Collect device logs using pymobiledevice3"""
        try:
            import sys
            
            # Create temporary directory for logs
            temp_dir = tempfile.mkdtemp()
            log_archive_path = os.path.join(temp_dir, f"{udid}.logarchive")
            
            # Use batch wrapper if available, otherwise use python -m
            pymobiledevice3_bat = get_lib_path('pymobiledevice3.bat')
            if os.path.exists(pymobiledevice3_bat):
                cmd = [pymobiledevice3_bat, 'syslog', 'collect', log_archive_path]
            else:
                cmd = [sys.executable, '-m', 'pymobiledevice3', 'syslog', 'collect', log_archive_path]
            
            log_message(f"📡 Running: {' '.join(cmd)}")
            
            # Hidden window config
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = subprocess.CREATE_NO_WINDOW
            
            process = subprocess.Popen(
                cmd,
                startupinfo=startupinfo,
                creationflags=creationflags,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True
            )
            
            try:
                stdout, stderr = process.communicate(timeout=120)
                
                if process.returncode == 0 and os.path.exists(log_archive_path):
                    log_message("✅ Log collection successful")
                    return log_archive_path
                else:
                    log_message(f"❌ Log collection failed (code: {process.returncode})")
                    if stderr:
                        log_message(f"Error: {stderr.strip()[:200]}")
                    return None
                    
            except subprocess.TimeoutExpired:
                log_message("❌ Log collection timeout")
                process.kill()
                return None
                
        except Exception as e:
            log_message(f"❌ Error collecting logs: {e}")
            return None

    def search_guid_in_logs_advanced(self, log_archive_path):
        """Search for GUID using PROVEN method from guid_extractor_proven.py - BLDatabaseManager scoring"""
        try:
            from collections import Counter

            # Find tracev3 file
            trace_file = os.path.join(log_archive_path, 'logdata.LiveData.tracev3')

            if not os.path.exists(trace_file):
                log_message("❌ tracev3 file not found")
                return None

            log_message("🔍 Scanning for BLDatabaseManager patterns...")

            # Read binary file
            with open(trace_file, 'rb') as f:
                data = f.read()

            # Look for multiple BLDatabaseManager patterns (proven method)
            db_patterns = [b'BLDatabaseManager', b'BLDatabase', b'BLDatabaseManager.sqlite']
            all_candidates = []

            for pattern in db_patterns:
                pattern_str = pattern.decode('utf-8', errors='replace')
                pos = 0
                found_count = 0

                while True:
                    pos = data.find(pattern, pos)
                    if pos == -1:
                        break

                    found_count += 1

                    # Search ±1024 bytes around match (validated parameter from proven method)
                    start = max(0, pos - 1024)
                    end = min(len(data), pos + len(pattern) + 1024)
                    window = data[start:end]

                    # Find GUIDs with proper pattern
                    guid_pat = re.compile(
                        rb'([0-9A-F]{8}[-][0-9A-F]{4}[-][0-9A-F]{4}[-][0-9A-F]{4}[-][0-9A-F]{12})',
                        re.IGNORECASE
                    )

                    for match in guid_pat.finditer(window):
                        raw_guid = match.group(1)
                        guid = raw_guid.decode('ascii').upper()
                        relative_pos = match.start() + start - pos

                        # Validate GUID structure
                        clean = guid.replace('0', '').replace('-', '')
                        if len(clean) >= 8:
                            all_candidates.append({
                                'guid': guid,
                                'position': relative_pos,
                                'pattern': pattern_str
                            })

                    pos += 1

                if found_count > 0:
                    log_message(f"  ✓ Found {found_count} occurrence(s) of '{pattern_str}'")

            if not all_candidates:
                log_message("❌ No valid GUIDs found")
                return None

            log_message(f"📊 Found {len(all_candidates)} valid candidates")

            # Score and rank GUIDs by recurrence and proximity (proven method)
            guid_list = [c['guid'] for c in all_candidates]
            counts = Counter(guid_list)

            # Calculate scores
            scored_guids = []
            for guid, count in counts.items():
                score = count * 10  # Base score from frequency

                # Bonus for being close to pattern (within ±100 bytes)
                close_positions = [c for c in all_candidates if c['guid'] == guid and abs(c['position']) <= 100]
                if close_positions:
                    score += len(close_positions) * 3

                # Bonus for being before the pattern (more likely to be path)
                before_positions = [c for c in all_candidates if c['guid'] == guid and c['position'] < 0]
                if before_positions:
                    score += len(before_positions) * 3

                scored_guids.append((guid, score, count))

            # Sort by score
            scored_guids.sort(key=lambda x: x[1], reverse=True)

            # Show top candidates
            log_message("📋 Top candidates:")
            for guid, score, count in scored_guids[:3]:
                log_message(f"  → {guid}: score={score}, count={count}")

            best_guid, best_score, best_count = scored_guids[0]

            # Confidence levels (from proven method)
            if best_score >= 30:
                log_message(f"✅ HIGH CONFIDENCE: {best_guid}")
            elif best_score >= 15:
                log_message(f"⚠️ MEDIUM CONFIDENCE: {best_guid}")
            else:
                log_message(f"⚠️ LOW CONFIDENCE: {best_guid}")

            return best_guid

        except Exception as e:
            log_message(f"❌ Error searching logs: {e}")
            import traceback
            traceback.print_exc()
            return None

    
    def _gather_log_files(self, log_path, max_files=100):
        """Gather all log files from log archive"""
        files = []
        
        # First add tracev3 if it exists
        tracev3 = os.path.join(log_path, "logdata.LiveData.tracev3")
        if os.path.exists(tracev3):
            files.append(tracev3)
        
        # Then add other log files
        exts = ('.log', '.txt', '.plist', '.trace')
        for root, _, fnames in os.walk(log_path):
            for fn in fnames:
                if len(files) >= max_files:
                    return files
                if fn.lower().endswith(exts):
                    full_path = os.path.join(root, fn)
                    if full_path not in files:
                        files.append(full_path)
        
        return files
    
    def _read_all_log_files(self, files, max_size=100 * 1024 * 1024):
        """Read all log files up to max_size"""
        bufs = []
        total = 0
        
        for f in files:
            try:
                sz = os.path.getsize(f)
                if total + sz > max_size:
                    continue
                
                with open(f, 'rb') as fp:
                    bufs.append(fp.read())
                total += sz
            except Exception:
                continue
        
        if not bufs:
            return None
        
        return b''.join(bufs)
   
   # ========== CONNECTION METHODS ==========

    def reboot_device_sync(self):
        try:
            ios_path = get_lib_path('ios.exe')
            if not os.path.exists(ios_path):
                print("❌ ios.exe not found in libs folder")
                return False
            
            cmd = [ios_path, 'reboot']
            result = run_subprocess_no_console(cmd, timeout=30)
            
            if result and result.returncode == 0:
                print("✅ Device reboot command sent successfully")
                return True
            else:
                print(f"⚠️ Reboot command failed")
                return True  # Return True anyway to continue
                
        except Exception as e:
            print(f"⚠️ Reboot error: {e}")
            return True  # Return True anyway to continue

    def wait_for_device_reconnect_sync(self, timeout):
        """Wait for device to reconnect (synchronous version)"""
        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.is_device_connected():
                    print("✅ Device reconnected after reboot")
                    return True
                time.sleep(5)  # Check every 5 seconds
            
            print("⚠️ Device did not reconnect within timeout period")
            return False
        except Exception as e:
            print(f"⚠️ Wait for reconnect error: {e}")
            return False

    # ========== THREAD-SAFE METHODS ==========
    
    def download_file_with_progress_thread(self, url, local_path, progress_signal):
        try:
            # Security check for proxy usage
            if security_monitor.check_proxy_usage():
                raise Exception("Proxy usage detected - Operation not allowed")
                
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(local_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        downloaded_size += len(chunk)
                        
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            progress_signal.emit(progress, self.get_random_hacking_text())
            
            return True
        except Exception as e:
            print(f"Error downloading file: {e}")
            return False

    def transfer_and_execute_sqlite_file_thread(self, local_file_path, progress_signal):
        try:
            # First check if device is still connected
            if not self.is_device_connected():
                raise Exception("Device disconnected during transfer")
            
            # Clear downloads folder first
            progress_signal.emit(10, "Cleaning device downloads...")
            if not self.clean_folder("Downloads"):
                print("⚠️ Could not clear downloads folder, continuing...")
            
            # Get the filename from the local path
            filename = os.path.basename(local_file_path)
            
            # Transfer file to Downloads folder
            progress_signal.emit(20, "Transferring activation file...")
            device_path = f"Downloads/{filename}"
            
            if not self.transfer_file_to_device(local_file_path, device_path):
                raise Exception("Failed to transfer file to device")
            
            print(f"✅ File transferred to {device_path}")
            
            # Wait a bit for processing to potentially start
            progress_signal.emit(30, "Initializing file processing...")
            time.sleep(5)
            
            return True
                
        except Exception as e:
            raise Exception(f"Transfer error: {str(e)}")

    def reboot_device_thread(self, progress_signal):
        try:
            # Check if ios.exe exists in libs folder
            ios_path = get_lib_path('ios.exe')
            
            if not os.path.exists(ios_path):
                raise Exception("ios.exe not found in libs folder")
            
            progress_signal.emit(95, self.get_random_hacking_text())
            
            # Execute reboot command
            cmd = [ios_path, 'reboot']
            result = run_subprocess_no_console(cmd, timeout=30)
            
            if result and result.returncode == 0:
                return True
            else:
                print(f"Reboot error")
                return True
                
        except Exception as e:
            print(f"Reboot error: {e}")
            return True

    def wait_for_device_reconnect_thread(self, timeout, progress_signal, worker):
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not worker.is_running:
                return False  # User cancelled
            
            elapsed = int(time.time() - start_time)
            remaining = timeout - elapsed
            
            if self.is_device_connected():
                print("Device reconnected after reboot")
                return True
            
            time.sleep(5)  # Check every 5 seconds
        
        print("Device did not reconnect within timeout period")
        return False

    def check_activation_status_thread(self):
        """Check device activation status - thread safe"""
        try:
            print("🔍 Checking device activation status...")
            
            ideviceinfo_path = get_lib_path('ideviceinfo.exe')
            
            if not os.path.exists(ideviceinfo_path):
                print("❌ ideviceinfo.exe not found")
                return "Unknown"
            
            # Get activation state from device
            result = run_subprocess_no_console([ideviceinfo_path, '-k', 'ActivationState'], timeout=15)
            
            if result and result.returncode == 0:
                activation_state = result.stdout.strip()
                print(f"📱 Device activation state: {activation_state}")
                
                if activation_state == "Activated":
                    return "Activated"
                elif activation_state == "Unactivated":
                    return "Unactivated"
                else:
                    return "Unknown"
            else:
                print(f"❌ Failed to get activation state")
                return "Unknown"
                
        except Exception as e:
            print(f"❌ Error checking activation status: {e}")
            return "Unknown"

    # ========== ACTIVATION PROCESS ==========
    
    def on_activate_button_clicked(self):
        """Handle activate button click - either request authorization or activate"""
        # Check if device needs authorization
        if not self.device_authorized:
            # Send authorization request directly
            self.send_authorization_request()
            return
        
        # Device is authorized - proceed with activation
        self.activate_device()
    
    def activate_device(self):
        """UPDATED ACTIVATION PROCESS with proper threading"""
        if not self.device_authorized:
            QMessageBox.warning(self, "Not Authorized", "Device is not authorized for activation.")
            return
        
        # # Security check before activation - including proxy detection
        if security_monitor.check_api_sniffing() or security_monitor.check_proxy_usage():
            QMessageBox.critical(self, "Security Violation", "Proxy usage detected! Application cannot run with proxy settings.")
            return
        
        # Show setup instruction dialog
        from gui.dialogs import SetupInstructionDialog
        instruction_dialog = SetupInstructionDialog(self)
        result = instruction_dialog.exec_()
        
        if result == QDialog.Rejected:
            print("User cancelled activation after reading instructions")
            return
        
        # Show progress bar and reset
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.activate_btn.setText("Starting activation process...")
        self.enable_activate_btn.emit(False)
        self.activation_in_progress = True

        # Create and start worker thread
        self.activation_worker = ActivationWorker(self)
        self.activation_worker.progress_updated.connect(self.on_update_progress)
        self.activation_worker.activation_finished.connect(self.on_activation_finished)
        self.activation_worker.guid_extracted.connect(self.on_guid_extracted)
        self.activation_worker.start()

    def on_guid_extracted(self, guid):
        log_message(f"📋 GUID extracted in main thread: {guid}")

    def on_activation_finished(self, success, message):
        if success:
            self.show_custom_activation_success()
        else:
            self.show_custom_activation_error(message)

        
    def check_authorization(self, model, serial):
        """Check if device is authorized using new server API"""
        try:
            # Security check for proxy usage
            if security_monitor.check_proxy_usage():
                return "proxy_detected"
            
            if model and serial and model != "N/A" and serial != "N/A":
                # Use new server API to check device status
                status_response = Api.get_device_status(serial)
                
                if status_response.get('success'):
                    device = status_response.get('device', {})
                    device_status = device.get('status', '')
                    
                    # Debug logging
                    log_message(f"[Auth Check] Device: {serial}, Status: '{device_status}'")
                    
                    if device_status == 'active':
                        self.log(f"✅ Device {serial} is authorized (active)", "success")
                        return "authorized"
                    
                    elif device_status == 'banned':
                        ban_reason = device.get('ban_reason', 'No reason provided')
                        self.log(f"🚫 Device {serial} is BANNED: {ban_reason}", "error")
                        return "banned"
                    
                    elif device_status == 'pending':
                        self.log(f"⏳ Device {serial} is pending admin approval", "warning")
                        return "pending"
                    
                    else:
                        self.log(f"❓ Device {serial} has unknown status: '{device_status}'", "warning")
                        log_message(f"[Auth Check] Full device response: {device}")
                        return "not_authorized"
                
                # Device not found in server - needs registration
                self.log(f"ℹ️ Device {serial} not registered", "warning")
                return "not_registered"
            
            return "error"
        except Exception as e:
            # Production: Don't break on server errors - show request button
            error_msg = str(e)[:100]
            self.log(f"⚠️ Server check failed: {error_msg}", "warning")
            # Return not_registered so user can request authorization
            return "not_registered"
    
    def setup_refresh_button(self):
        """Create and setup refresh authorization button"""
        if not hasattr(self, 'refresh_btn'):
            self.refresh_btn = QPushButton("🔄 Refresh Status")
            self.refresh_btn.setObjectName("refresh_btn")
            self.refresh_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {self.TEXT_SECONDARY};
                    border: 1px solid {self.BORDER};
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {self.BG_INPUT};
                    color: {self.TEXT_PRIMARY};
                    border-color: {self.TEXT_SECONDARY};
                }}
                QPushButton:pressed {{
                    background-color: {self.BG_CARD};
                }}
            """)
            self.refresh_btn.clicked.connect(self.on_refresh_clicked)
            self.refresh_btn.setCursor(Qt.PointingHandCursor)
            
            # Add to layout after activate button
            if self.centralWidget() and self.centralWidget().layout():
                layout = self.centralWidget().layout()
                # Find activate button index
                for i in range(layout.count()):
                    widget = layout.itemAt(i).widget()
                    if widget and widget.objectName() == "activate_btn":
                        layout.insertWidget(i + 1, self.refresh_btn)
                        break
                else:
                    layout.addWidget(self.refresh_btn)
    
    def on_refresh_clicked(self):
        """Handle refresh button click"""
        if self.current_serial and self.current_product_type:
            self.log("🔄 Manually refreshing authorization status...", "info")
            self.refresh_btn.setEnabled(False)
            self.refresh_btn.setText("⏳ Checking...")
            
            def refresh_thread():
                # Force recheck authorization
                self.authorization_checked = False
                self.check_device_authorization(self.current_product_type, self.current_serial, force=True)
                
                # Re-enable button after 2 seconds
                QTimer.singleShot(2000, lambda: self.refresh_btn.setEnabled(True))
                QTimer.singleShot(2000, lambda: self.refresh_btn.setText("🔄 Refresh Status"))
            
            threading.Thread(target=refresh_thread, daemon=True).start()
        else:
            self.log("⚠️ No device connected", "warning")
    
    def _refresh_authorization(self):
        """Periodic refresh of authorization status"""
        # Only refresh if device is connected but not yet authorized
        if (self.current_serial and self.current_product_type and 
            not self.device_authorized and 
            self.status_value.text() in ["Connected", "Not Registered - Click to Request", "Pending Admin Approval"]):
            print("🔄 Auto-refreshing authorization status...")
            self.check_device_authorization(self.current_product_type, self.current_serial, force=True)
    
    def send_authorization_request(self):
        """Send authorization request to admin via Telegram"""
        serial = self.current_serial
        model = self.model_value.text()
        prd = self.current_product_type
        
        if serial and prd:
            self.log(f"📨 Sending authorization request for {serial}...", "info")
            
            # Send authorization request to server
            try:
                import requests
                response = requests.post(
                    f"{config.SERVER_URL}/api/request-authorization",
                    json={
                        "sn": serial,
                        "prd": prd,
                        "model": model or prd
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    self.log("✅ Request sent to admin.", "success")
                    
                    # Show success message with contact option
                    msg_box = QMessageBox(self)
                    msg_box.setWindowTitle("Request Sent")
                    msg_box.setText("Authorization request has been sent to admin.\nYou will be notified once approved.")
                    msg_box.setInformativeText("You can also contact admin directly via Telegram:")
                    
                    contact_btn = msg_box.addButton("Contact Admin", QMessageBox.ActionRole)
                    ok_btn = msg_box.addButton(QMessageBox.Ok)
                    
                    msg_box.exec_()
                    
                    if msg_box.clickedButton() == contact_btn:
                        import webbrowser
                        webbrowser.open("https://t.me/sawyelinmsz")
                else:
                    self.log("⚠️ Server error - please contact admin.", "warning")
                    self._show_contact_admin_dialog("Server Unavailable", "Unable to reach server. Please contact admin directly.")
                        
            except requests.exceptions.Timeout:
                self.log("⚠️ Request timeout - please contact admin.", "warning")
                self._show_contact_admin_dialog("Request Timeout", "Server is taking too long to respond. Please contact admin directly.")
            except requests.exceptions.ConnectionError:
                self.log("⚠️ Connection error - please contact admin.", "warning")
                self._show_contact_admin_dialog("Connection Error", "Cannot connect to server. Please contact admin directly.")
            except Exception as e:
                self.log(f"⚠️ Error: {str(e)[:100]}", "warning")
                self._show_contact_admin_dialog("Request Failed", "Unable to send request. Please contact admin directly.")
    
    def _show_contact_admin_dialog(self, title, message):
        """Show dialog with contact admin option"""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setInformativeText("Please contact admin directly via Telegram:")
        
        contact_btn = msg_box.addButton("Contact Admin", QMessageBox.ActionRole)
        ok_btn = msg_box.addButton(QMessageBox.Ok)
        
        msg_box.exec_()
        
        if msg_box.clickedButton() == contact_btn:
            import webbrowser
            webbrowser.open("https://t.me/sawyelinmsz")
    
    def fetch_device_model(self, product_type):
        """Fetch device model name - uses local cache or GitHub CDN"""
        try:
            # Security check for proxy usage
            if security_monitor.check_proxy_usage():
                return "Proxy usage detected"
            
            # Check cache first (but skip if cached value contains "Unsupported")
            if product_type in self.cached_models:
                cached = self.cached_models[product_type]
                if "Unsupported" not in cached:
                    return cached
                # Clear bad cache entry
                del self.cached_models[product_type]
            
            if product_type and product_type != "N/A":
                # Always return friendly name for known models
                # GitHub CDN availability is checked during activation
                model_name = self.get_friendly_model_name(product_type)
                self.cached_models[product_type] = model_name
                print(f'✅ Device model: {model_name}')
                return model_name
            
            return "N/A"
        except Exception as e:
            print(f"❌ Error fetching device model: {e}")
            # Return the product_type itself instead of "Error"
            return product_type if product_type else "Unknown"
    
    def get_friendly_model_name(self, product_type):
        """Convert product type to friendly name - dynamically from device or mapping"""
        # First check if we have HardwareModel or DeviceClass from device info
        if hasattr(self, 'device_info') and self.device_info:
            # HardwareModel is most accurate (e.g., J217AP for iPad Air 3)
            hardware_model = self.device_info.get('HardwareModel')
            if hardware_model and hardware_model != 'N/A':
                # Map hardware model to friendly name
                friendly = self._get_name_from_hardware(hardware_model)
                if friendly:
                    return friendly
            
            # Try DeviceClass (e.g., iPad, iPhone)
            device_class = self.device_info.get('DeviceClass')
            if device_class and device_class != 'N/A':
                # Don't use generic "iPhone OS" - use our mapping
                pass
        
        # Use ProductType mapping for specific device names
        return self._get_name_from_product_type(product_type)
    
    def _get_name_from_hardware(self, hardware_model):
        """Map hardware model to friendly name"""
        hardware_map = {
            # iPad Air 3rd gen
            'J217AP': 'iPad Air (3rd gen)',
            'J218AP': 'iPad Air (3rd gen)',
            # iPad 8th gen
            'J171AP': 'iPad (8th gen)',
            'J172AP': 'iPad (8th gen)',
            # iPad 9th gen
            'J181AP': 'iPad (9th gen)',
            'J182AP': 'iPad (9th gen)',
            # iPad Air 4th gen
            'J307AP': 'iPad Air (4th gen)',
            'J308AP': 'iPad Air (4th gen)',
            # iPad Air 5th gen
            'J407AP': 'iPad Air (5th gen)',
            'J408AP': 'iPad Air (5th gen)',
            # iPhone 11 series
            'N104AP': 'iPhone 11',
            'D421AP': 'iPhone 11 Pro',
            'D431AP': 'iPhone 11 Pro Max',
            # iPhone 12 series
            'D52GAP': 'iPhone 12 mini',
            'D53GAP': 'iPhone 12',
            'D53PAP': 'iPhone 12 Pro',
            'D54PAP': 'iPhone 12 Pro Max',
            # iPhone 13 series
            'D16AP': 'iPhone 13 mini',
            'D17AP': 'iPhone 13',
            'D63AP': 'iPhone 13 Pro',
            'D64AP': 'iPhone 13 Pro Max',
            # iPhone 14 series
            'D27AP': 'iPhone 14',
            'D28AP': 'iPhone 14 Plus',
            'D73AP': 'iPhone 14 Pro',
            'D74AP': 'iPhone 14 Pro Max',
        }
        return hardware_map.get(hardware_model)
    
    def _get_name_from_product_type(self, product_type):
        """Map ProductType to friendly name"""
        # Common iPad models
        if product_type == "iPad11,3" or product_type == "iPad11,4":
            return "iPad Air (3rd gen)"
        elif product_type == "iPad11,6" or product_type == "iPad11,7":
            return "iPad (8th gen)"
        elif product_type == "iPad12,1" or product_type == "iPad12,2":
            return "iPad (9th gen)"
        elif product_type == "iPad13,1" or product_type == "iPad13,2":
            return "iPad Air (4th gen)"
        elif product_type == "iPad13,4" or product_type == "iPad13,5" or product_type == "iPad13,6" or product_type == "iPad13,7":
            return "iPad Pro 11-inch (3rd gen)"
        elif product_type == "iPad13,8" or product_type == "iPad13,9" or product_type == "iPad13,10" or product_type == "iPad13,11":
            return "iPad Pro 12.9-inch (5th gen)"
        # iPhone models
        elif product_type == "iPhone12,1":
            return "iPhone 11"
        elif product_type == "iPhone12,3":
            return "iPhone 11 Pro"
        elif product_type == "iPhone12,5":
            return "iPhone 11 Pro Max"
        elif product_type == "iPhone13,1":
            return "iPhone 12 mini"
        elif product_type == "iPhone13,2":
            return "iPhone 12"
        elif product_type == "iPhone13,3":
            return "iPhone 12 Pro"
        elif product_type == "iPhone13,4":
            return "iPhone 12 Pro Max"
        elif product_type == "iPhone14,2":
            return "iPhone 13 Pro"
        elif product_type == "iPhone14,3":
            return "iPhone 13 Pro Max"
        elif product_type == "iPhone14,4":
            return "iPhone 13 mini"
        elif product_type == "iPhone14,5":
            return "iPhone 13"
        elif product_type == "iPhone14,7":
            return "iPhone 14"
        elif product_type == "iPhone14,8":
            return "iPhone 14 Plus"
        elif product_type == "iPhone15,2":
            return "iPhone 14 Pro"
        elif product_type == "iPhone15,3":
            return "iPhone 14 Pro Max"
        # Add more mappings as needed
        else:
            return product_type.replace(",", " ")

    def get_random_hacking_text(self):
        """Generate random hacking-like text for UI display"""
        hacking_phrases = [
            "Initializing secure connection...",
            "Bypassing security protocols...",
            "Establishing encrypted tunnel...",
            "Decrypting security tokens...",
            "Accessing secure partition...",
            "Verifying cryptographic signatures...",
            "Establishing handshake protocol...",
            "Scanning system vulnerabilities...",
            "Injecting security payload...",
            "Establishing secure shell...",
            "Decrypting firmware keys...",
            "Accessing secure boot chain...",
            "Verifying system integrity...",
            "Establishing secure communication...",
            "Bypassing hardware restrictions..."
        ]
        return random.choice(hacking_phrases)

    def afc_client_operation(self, operation, *args):
        """Execute AFC client operations"""
        try:
            afcclient_path = get_lib_path('afcclient.exe')
            
            if not os.path.exists(afcclient_path):
                raise Exception("afcclient.exe not found in libs folder")
            
            cmd = [afcclient_path, operation] + list(args)
            result = run_subprocess_no_console(cmd, timeout=30)
            
            if result and result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr if result else "Unknown error"
                
        except Exception as e:
            return False, str(e)

    def transfer_file_to_device(self, local_file_path, device_path):
        """Transfer file to device using AFC client"""
        try:
            success, output = self.afc_client_operation('put', local_file_path, device_path)
            return success
        except Exception as e:
            print(f"Error transferring file: {e}")
            return False
    
    def download_file_from_device(self, device_path, local_path):
        """Download file from device using pymobiledevice3"""
        try:
            import subprocess
            from utils.helpers import get_lib_path
            
            # Use pymobiledevice3 to pull file
            cmd = ['pymobiledevice3', 'afc', 'pull', device_path, local_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and os.path.exists(local_path):
                return True
            else:
                print(f"Failed to download: {result.stderr}")
                return False
        except Exception as e:
            print(f"Error downloading file: {e}")
            return False
    
    def copy_file_on_device(self, source_path, dest_path):
        """Copy file from one location to another on device"""
        try:
            import tempfile
            
            print(f"📋 Copying {source_path} to {dest_path}...")
            
            # Download from source
            with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as tmp:
                tmp_path = tmp.name
            
            if not self.download_file_from_device(source_path, tmp_path):
                print(f"❌ Failed to download {source_path}")
                return False
            
            # Upload to destination
            if not self.transfer_file_to_device(tmp_path, dest_path):
                print(f"❌ Failed to upload to {dest_path}")
                os.unlink(tmp_path)
                return False
            
            # Cleanup
            os.unlink(tmp_path)
            print(f"✅ Successfully copied to {dest_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error copying file: {e}")
            return False

    def is_device_connected(self):
        """Check if device is still connected"""
        try:
            ideviceinfo_path = get_lib_path('ideviceinfo.exe')
            if os.path.exists(ideviceinfo_path):
                result = run_subprocess_no_console([ideviceinfo_path], timeout=5)
                return result and result.returncode == 0 and result.stdout.strip()
            return False
        except:
            return False

    def send_guid_to_api(self, guid):
        """Send GUID to server - now handled during activation"""
        # This method is kept for backward compatibility
        # GUID is now sent during the activation process
        log_message(f"📤 GUID extracted: {guid}")
        log_message("✅ GUID will be sent during activation process")
        return True

    def get_device_udid(self):
        """Get device UDID"""
        try:
            # Try idevice_id first
            idevice_id_path = get_lib_path('idevice_id.exe')
            if os.path.exists(idevice_id_path):
                result = run_subprocess_no_console([idevice_id_path, '-l'], timeout=10)
                if result and result.returncode == 0 and result.stdout.strip():
                    udids = result.stdout.strip().split('\n')
                    return udids[0].strip()
            
            # Try ideviceinfo as fallback
            ideviceinfo_path = get_lib_path('ideviceinfo.exe')
            if os.path.exists(ideviceinfo_path):
                result = run_subprocess_no_console([ideviceinfo_path, '-k', 'UniqueDeviceID'], timeout=10)
                if result and result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            
            return None
            
        except Exception as e:
            print(f"Error getting device UDID: {e}")
            return None

    def show_custom_activation_success(self):
        """Show custom activation success message box"""
        self.progress_bar.setVisible(False)
        self.activation_in_progress = False
        
        dialog = ActivationResultDialog(
            "🎉 Activation Successful!",
            "Your device has been successfully activated!\n\nThe activation process completed successfully. Your device is now ready to use.",
            is_success=True,
            parent=self
        )
        dialog.exec_()
        
        # Update status
        self.status_value.setText("Activation Complete")
        self.status_value.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 14px;")

    def show_custom_activation_error(self, error_message):
        """Show custom activation error message box"""
        self.progress_bar.setVisible(False)
        self.enable_activate_btn.emit(True)
        self.activation_in_progress = False
        
        dialog = ActivationResultDialog(
            "🚨 Activation Error",
            f"An error occurred during activation.\n\nError: {error_message}\n\nPlease try again.",
            is_success=False,
            parent=self
        )
        dialog.exec_()
        
        # Update status
        self.status_value.setText("Activation Error")
        self.status_value.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 14px;")

    @pyqtSlot(str)
    def on_model_received(self, model_name):
        self.model_value.setText(model_name)
    
    @pyqtSlot(str, str)
    def on_show_auth_dialog(self, model_name, serial):
        """Show authorization dialog from main thread"""
        print(f"Showing authorization dialog for {model_name} - {serial}")
        message = f"Your device {model_name} (SN: {serial}) is not authorized.\n\nPlease contact admin for activation."
        
        dialog = CustomMessageBox(
            "Authorization Required",
            message,
            serial,
            self
        )
        
        result = dialog.exec_()
        
        if result == QDialog.Accepted:
            print("User clicked Request Authorization")
            
            # Send Telegram notification to admin
            try:
                import requests
                telegram_url = f"{config.SERVER_URL}/api/request-authorization"
                response = requests.post(telegram_url, json={
                    "sn": serial,
                    "prd": self.current_product_type or model_name,
                    "model": model_name
                }, timeout=5)
                
                if response.status_code == 200:
                    print("✅ Authorization request sent to admin")
                    
                    # Show success message with contact option
                    msg_box = QMessageBox(self)
                    msg_box.setWindowTitle("Request Sent")
                    msg_box.setText("Authorization request has been sent to admin.\nYou will be notified once approved.")
                    msg_box.setInformativeText("You can also contact admin directly via Telegram:")
                    
                    # Add custom button to open Telegram
                    contact_btn = msg_box.addButton("Contact Admin", QMessageBox.ActionRole)
                    ok_btn = msg_box.addButton(QMessageBox.Ok)
                    
                    msg_box.exec_()
                    
                    # Check which button was clicked
                    if msg_box.clickedButton() == contact_btn:
                        webbrowser.open("https://t.me/sawyelinmsz")
                else:
                    print("⚠️ Failed to send authorization request")
                    
                    # Show error with contact option
                    msg_box = QMessageBox(self)
                    msg_box.setIcon(QMessageBox.Warning)
                    msg_box.setWindowTitle("Request Failed")
                    msg_box.setText("Failed to send authorization request.")
                    msg_box.setInformativeText("Please contact admin directly via Telegram:")
                    
                    contact_btn = msg_box.addButton("Contact Admin", QMessageBox.ActionRole)
                    ok_btn = msg_box.addButton(QMessageBox.Ok)
                    
                    msg_box.exec_()
                    
                    if msg_box.clickedButton() == contact_btn:
                        webbrowser.open("https://t.me/sawyelinmsz")
            except Exception as e:
                print(f"❌ Error sending authorization request: {e}")
                
                # Show error with contact option
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setWindowTitle("Request Failed")
                msg_box.setText("Failed to send authorization request.")
                msg_box.setInformativeText("Please contact admin directly via Telegram:")
                
                contact_btn = msg_box.addButton("Contact Admin", QMessageBox.ActionRole)
                ok_btn = msg_box.addButton(QMessageBox.Ok)
                
                msg_box.exec_()
                
                if msg_box.clickedButton() == contact_btn:
                    webbrowser.open("https://t.me/sawyelinmsz")
            
            # Keep activate button disabled until device is authorized
            self.enable_activate_btn.emit(False)
        else:
            print("User canceled the authorization process")
            # Keep activate button disabled
            self.enable_activate_btn.emit(False)
    
    @pyqtSlot(str, str)
    def on_update_status_label(self, status_text, color):
        """Update status label from main thread"""
        self.status_value.setText(status_text)
        self.status_value.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 14px;")
    
    @pyqtSlot(int, str)
    def on_update_progress(self, value, text):
        """Update progress bar and label from main thread"""
        self.progress_bar.setValue(value)
        
        # Update progress label if it exists
        if hasattr(self, 'progress_label'):
            self.progress_label.setText(text)
        
        # Also update button text for backward compatibility
        if value < 100:
            self.activate_btn.setText(text)
    #   TODO click to copy  
    def copy_to_clipboard(self, text, label):
        print(f"Copying to clipboard: {text}")
        """Copy text to clipboard and show temporary feedback"""
        if text != "N/A" and text != "Unknown" and text != "Unknown Model" and not text.startswith("API Error"):
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            
            original_text = label.text()
            original_style = label.styleSheet()
            
            label.setText("Copied!")
            label.setStyleSheet("""
                color: #27ae60; 
                font-weight: bold;
                font-size: 14px;
                padding: 5px;
                border: 1px solid #27ae60;
                border-radius: 3px;
                background-color: #d5f4e6;
            """)
            
            QTimer.singleShot(2000, lambda: self.restore_text(label, original_text, original_style))
    
    def restore_text(self, label, original_text, original_style):
        """Restore the original label text and style"""
        label.setText(original_text)
        label.setStyleSheet(original_style)
        
    def setup_device_monitor(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_device_status)
        self.timer.start(2000)
        
    def check_device_status(self):
        if self.activation_in_progress:
            return
        
        # Track last check time for debug panel
        import time
        self.last_device_check_time = time.time()

        # === FUNCIÓN INTERNA BIEN DEFINIDA ===
        def device_check_thread():
            try:
                ideviceinfo_path = get_lib_path('ideviceinfo.exe')
                idevice_id_path = get_lib_path('idevice_id.exe')

                # Primero intenta con ideviceinfo (da toda la info)
                if os.path.exists(ideviceinfo_path):
                    result = run_subprocess_no_console([ideviceinfo_path], timeout=10)
                    if result and result.returncode == 0 and result.stdout.strip():
                        self.parse_device_info(result.stdout)
                        self.device_connected.emit(True)
                        return

                # Si no, al menos detecta conexión básica con idevice_id
                if os.path.exists(idevice_id_path):
                    result = run_subprocess_no_console([idevice_id_path, '-l'], timeout=8)
                    if result and result.returncode == 0 and result.stdout.strip():
                        print("¡Dispositivo detectado! (solo conexión básica)")
                        self.device_connected.emit(True)
                        QTimer.singleShot(0, self.update_basic_connection)
                        return

                # Si llega aquí → no hay dispositivo
                self.device_connected.emit(False)

            except Exception as e:
                print(f"Error en detección: {e}")
                self.device_connected.emit(False)

        # === LANZAR EN HILO ===
        threading.Thread(target=device_check_thread, daemon=True).start()   
    def parse_device_info(self, output):
        self.device_info = {}
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                self.device_info[key] = value
        
        QTimer.singleShot(0, self.update_device_info)
    
    def update_device_info(self):
        try:
            serial = self.device_info.get('SerialNumber', 'N/A')
            ios_version = self.device_info.get('ProductVersion', 'N/A')
            imei = self.device_info.get('InternationalMobileEquipmentIdentity', 'N/A')
            product_type = self.device_info.get('ProductType', 'N/A')
            
            if serial == 'N/A' and 'UniqueDeviceID' in self.device_info:
                serial = self.device_info['UniqueDeviceID'][-8:]
            
            # Check if device has changed
            device_changed = (serial != self.current_serial or 
                            product_type != self.current_product_type)
            
            if device_changed:
                self.log(f"New device detected: {serial}", "success")
                self.current_serial = serial
                self.current_product_type = product_type
                self.authorization_checked = False
                self.device_authorized = False
                self._pending_shown = False  # Reset flags for new device
                self._banned_shown = False
                
                # Update basic info
                self.serial_value.setText(serial)
                self.ios_value.setText(ios_version)
                self.imei_value.setText(imei)
                self.status_value.setText("Connected")
                self.status_value.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 14px;")
                
                # Initially disable activate button until we know authorization status
                self.enable_activate_btn.emit(False)
                
                # Fetch and display device model from API only if device changed
                if product_type != 'N/A':
                    # Show "Loading..." while fetching model name
                    self.model_value.setText("Loading...")
                    self.log(f"ProductType: {product_type}", "info")
                    
                    def fetch_model():
                        model_name = self.fetch_device_model(product_type)
                        # Use signal to update UI from main thread
                        self.model_received.emit(model_name)
                        
                        # After model is received, check authorization
                        if model_name != "N/A" and not model_name.startswith("API Error"):
                            self.check_device_authorization(model_name, serial)
                    
                    threading.Thread(target=fetch_model, daemon=True).start()
                else:
                    self.model_value.setText("N/A")
                    self.log("No ProductType found", "warning")
                
            # else:
            #     # Same device, no need to update UI
            #     print(f"Same device connected: {serial}, no UI update needed")
            
        except Exception as e:
            print(f"Error updating UI: {e}")
    
    def check_device_authorization(self, model_name, serial, force=False):
        """Check device authorization. Set force=True to recheck even if already checked."""
        if not self.authorization_checked or force:
            print(f"Checking authorization for device: {model_name} - {serial}")
            
            def check_auth():
                auth_status = self.check_authorization(model_name, serial)
                
                if auth_status == "authorized":
                    print(f"✅ Device {serial} is AUTHORIZED!")
                    self.device_authorized = True
                    self._pending_shown = False  # Reset pending flag
                    # Update status to "Bypass Authorized" and enable activate button
                    self.update_status_label.emit("Bypass Authorized", "#27ae60")
                    self.enable_activate_btn.emit(True)
                
                elif auth_status == "banned":
                    print(f"🚫 Device {serial} is BANNED!")
                    self.device_authorized = False
                    self._pending_shown = False  # Reset pending flag
                    # Update status to show banned state
                    self.update_status_label.emit("Device Banned", "#ff4444")
                    self.enable_activate_btn.emit(False)
                    # Only show message once
                    if not hasattr(self, '_banned_shown') or not self._banned_shown:
                        self._banned_shown = True
                        QTimer.singleShot(500, lambda: QMessageBox.critical(
                            self, 
                            "Device Banned", 
                            f"This device (SN: {serial}) has been banned from activation.\n\n"
                            "Please contact support for more information."
                        ))
                
                elif auth_status == "pending":
                    print(f"⏳ Device {serial} is PENDING approval")
                    self.device_authorized = False
                    # Update status to show pending state
                    self.update_status_label.emit("Pending Admin Approval", "#ffaa00")
                    self.enable_activate_btn.emit(False)
                    # Only show message once (not on auto-refresh)
                    if not hasattr(self, '_pending_shown') or not self._pending_shown:
                        self._pending_shown = True
                        QTimer.singleShot(500, lambda: QMessageBox.information(
                            self, 
                            "Pending Approval", 
                            f"Your device (SN: {serial}) is pending admin approval.\n\n"
                            "Please wait for the administrator to approve your request.\n"
                            "Click 'Refresh Status' button to check if approved."
                        ))
                    
                elif auth_status == "not_authorized" or auth_status == "not_registered":
                    print(f"Device {serial} not registered. Button will show 'Request Authorization'.")
                    self.device_authorized = False
                    self._pending_shown = False  # Reset pending flag
                    # Update status and change button to request mode
                    self.update_status_label.emit("Not Registered - Click to Request", "#ffaa00")
                    self.enable_activate_btn.emit(False)  # This will trigger button text change
                    
                elif auth_status == "proxy_detected":
                    print(f"Proxy detected for device {serial}! Blocking access.")
                    # Show proxy warning and block access
                    self.show_proxy_warning_message()
                    # Keep status as "Connected" and button disabled
                    self.update_status_label.emit("Security Violation", "#e74c3c")
                    self.enable_activate_btn.emit(False)
                    
                elif auth_status == "folder_not_found":
                    print(f"Device folder for {model_name} not found on server.")
                    # Show custom message for folder not found
                    self.show_folder_not_found_message(model_name, serial)
                    # Keep status as "Connected" and button disabled
                    self.update_status_label.emit("Connected", "#27ae60")
                    self.enable_activate_btn.emit(False)
                    
                else:
                    print(f"Device {serial} authorization status unknown or error.")
                    # Keep status as "Connected" and button disabled for unknown/error cases
                    self.update_status_label.emit("Connected", "#27ae60")
                    self.enable_activate_btn.emit(False)
                
                self.authorization_checked = True
            
            threading.Thread(target=check_auth, daemon=True).start()
    
    def show_proxy_warning_message(self):
        """Show proxy warning message"""
        def show_dialog():
            msg = QMessageBox(self)
            msg.setWindowTitle("Security Violation")
            msg.setText("Proxy usage detected!\n\nThis application cannot run with proxy settings for security reasons.\n\nPlease disable any proxy settings and try again.")
            msg.setIcon(QMessageBox.Critical)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        
        QTimer.singleShot(0, show_dialog)
    
    def show_folder_not_found_message(self, model_name, serial):
        """Show custom message when device folder is not found"""
        def show_dialog():
            msg = QMessageBox(self)
            msg.setWindowTitle("Device Not Ready")
            msg.setText(f"Your {model_name} device will be ready in a bit.\n\nPlease check back later.")
            msg.setInformativeText(f"Serial: {serial}")
            msg.setIcon(QMessageBox.Information)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        
        QTimer.singleShot(0, show_dialog)

    def update_basic_connection(self):
        """Update UI when device is connected but we can't get detailed info"""
        # Only update if this is a new basic connection
        if self.current_serial != "basic_connection":
            self.current_serial = "basic_connection"
            self.current_product_type = "Unknown"
            self.device_authorized = False
            
            self.serial_value.setText("Connected")
            self.ios_value.setText("Unknown")
            self.imei_value.setText("Unknown")
            self.model_value.setText("Unknown")
            self.status_value.setText("Connected (Limited Info)")
            self.status_value.setStyleSheet("color: #f39c12; font-weight: bold; font-size: 14px;")
            self.enable_activate_btn.emit(False)
            print("Basic connection detected - limited info available")
        
    def clear_device_info(self):
        """Clear device info when disconnected"""
        if self.current_serial is not None:
            self.current_serial = None
            self.current_product_type = None
            self.authorization_checked = False
            self.device_authorized = False
            
            self.serial_value.setText("N/A")
            self.ios_value.setText("N/A")
            self.imei_value.setText("N/A")
            self.model_value.setText("N/A")
            self.status_value.setText("Disconnected")
            self.status_value.setStyleSheet("color: #e74c3c; font-size: 14px;")
            self.enable_activate_btn.emit(False)
            print("Device disconnected - cleared UI")

    @pyqtSlot(bool)
    def on_device_connected(self, connected):
        if not connected:
            QTimer.singleShot(0, self.clear_device_info)
