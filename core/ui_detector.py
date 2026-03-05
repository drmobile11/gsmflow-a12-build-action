#!/usr/bin/env python3
"""
UI Detector - PyQt5 wrapper around DeviceManager
Separates UI logic from device detection logic
"""

from PyQt5.QtCore import QObject, pyqtSignal, QTimer
import threading

from core.device import DeviceManager
from core.api import Api

class UIDetector(QObject):
    """PyQt5 UI wrapper for device detection"""
    
    # Signals for UI updates
    device_connected = pyqtSignal(bool)
    model_received = pyqtSignal(str)
    serial_received = pyqtSignal(str)
    ios_version_received = pyqtSignal(str)
    imei_received = pyqtSignal(str)
    status_updated = pyqtSignal(str, str)  # status, color
    enable_activate_btn = pyqtSignal(bool)
    authorization_result = pyqtSignal(bool, str)  # authorized, message
    
    def __init__(self, ui_components=None):
        super().__init__()
        self.device = DeviceManager()
        self.ui_components = ui_components
        self.authorization_checked = False
        self.device_authorized = False
        self.activation_in_progress = False
        
        # Connect signals to UI slots if provided
        if ui_components:
            self._connect_ui_signals()
    
    def _connect_ui_signals(self):
        """Connect signals to UI component slots"""
        ui = self.ui_components
        self.model_received.connect(ui.model_value.setText)
        self.serial_received.connect(ui.serial_value.setText)
        self.ios_version_received.connect(ui.ios_value.setText)
        self.imei_received.connect(ui.imei_value.setText)
        self.status_updated.connect(self._update_status_label)
        self.enable_activate_btn.connect(ui.activate_btn.setEnabled)
    
    def _update_status_label(self, status, color):
        """Update status label with color"""
        if hasattr(self.ui_components, 'status_value'):
            self.ui_components.status_value.setText(status)
            self.ui_components.status_value.setStyleSheet(f"color: {color}; font-weight: bold;")
    
    def check_device_connection(self):
        """Check if device is connected (threaded)"""
        threading.Thread(target=self._check_device_thread, daemon=True).start()
    
    def _check_device_thread(self):
        """Background thread for device detection"""
        try:
            if self.device.is_device_connected():
                device_info = self.device.get_device_info()
                if device_info:
                    self._emit_device_info(device_info)
                    self.device_connected.emit(True)
                else:
                    self.device_connected.emit(False)
            else:
                self.device_connected.emit(False)
        except Exception as e:
            print(f"Error in device check: {e}")
            self.device_connected.emit(False)
    
    def _emit_device_info(self, device_info):
        """Emit device info to UI"""
        serial = device_info.get('SerialNumber', 'N/A')
        if serial == 'N/A' and 'UniqueDeviceID' in device_info:
            serial = device_info['UniqueDeviceID'][-8:]
        
        ios_version = device_info.get('ProductVersion', 'N/A')
        imei = device_info.get('InternationalMobileEquipmentIdentity', 'N/A')
        product_type = device_info.get('ProductType', 'N/A')
        
        # Check if device changed
        device_changed = (serial != self.device.current_serial or 
                         product_type != self.device.current_product_type)
        
        if device_changed:
            print(f"Device changed! New device detected: {serial}")
            self.authorization_checked = False
            self.device_authorized = False
            
            # Emit basic info
            self.serial_received.emit(serial)
            self.ios_version_received.emit(ios_version)
            self.imei_received.emit(imei)
            self.status_updated.emit("Connected", "#27ae60")
            self.enable_activate_btn.emit(False)
            
            # Fetch model name
            if product_type != 'N/A':
                self.model_received.emit("Loading...")
                
                def fetch_model():
                    model_name = self.device.get_model_name()
                    self.model_received.emit(model_name)
                    # Check authorization after model is received
                    if model_name != "N/A":
                        self.check_authorization(model_name, serial)
                
                threading.Thread(target=fetch_model, daemon=True).start()
    
    def check_authorization(self, model_name, serial):
        """Check if device is authorized"""
        if self.authorization_checked:
            return
        
        print(f"Checking authorization for device: {model_name} - {serial}")
        
        try:
            # Use new server API to check device status
            status_response = Api.get_device_status(serial)
            
            if status_response.get('success'):
                device = status_response.get('device', {})
                if device.get('status') == 'active':
                    print(f"✅ Device {serial} is authorized")
                    self.device_authorized = True
                    self.authorization_result.emit(True, "Device is authorized")
                    self.enable_activate_btn.emit(True)
                elif device.get('status') == 'banned':
                    print(f"❌ Device {serial} is banned")
                    self.device_authorized = False
                    self.authorization_result.emit(False, "Device is banned")
                    self.enable_activate_btn.emit(False)
            else:
                # Device not found - allow activation (will register on first use)
                print(f"ℹ️ Device {serial} not registered yet - will register on activation")
                self.device_authorized = True
                self.authorization_result.emit(True, "Device not registered - will register on activation")
                self.enable_activate_btn.emit(True)
        
        except Exception as e:
            print(f"⚠️ Authorization check error: {e}")
            # Allow activation even if server check fails
            self.device_authorized = True
            self.authorization_result.emit(True, "Authorization check failed - allowing activation")
            self.enable_activate_btn.emit(True)
        
        self.authorization_checked = True
    
    def get_device_manager(self):
        """Get the underlying DeviceManager instance"""
        return self.device
    
    @property
    def current_serial(self):
        return self.device.current_serial
    
    @property
    def current_product_type(self):
        return self.device.current_product_type
