#!/usr/bin/env python3
"""
Pure device detection logic - no UI dependencies
Handles iOS device communication via ideviceinfo, pymobiledevice3
"""

import os
import re
import sys
import time
import json
import random
import shutil
import zipfile
import datetime
import subprocess
import threading
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helpers import get_lib_path, run_subprocess_no_console
from core.api import Api

class DeviceManager:
    """Manages iOS device detection and communication without UI"""
    
    def __init__(self):
        self.device_info = {}
        self.current_serial = None
        self.current_product_type = None
        self.cached_models = {}
        self.extracted_guid = None
        
    def get_device_info(self):
        """Get device info from ideviceinfo"""
        try:
            ideviceinfo_path = get_lib_path('ideviceinfo.exe')
            if not os.path.exists(ideviceinfo_path):
                print("❌ ideviceinfo.exe not found")
                return None
                
            result = run_subprocess_no_console([ideviceinfo_path], timeout=10)
            if result and result.returncode == 0 and result.stdout.strip():
                self._parse_device_info(result.stdout)
                return self.device_info
            return None
        except Exception as e:
            print(f"Error getting device info: {e}")
            return None
    
    def _parse_device_info(self, output):
        """Parse ideviceinfo output"""
        self.device_info = {}
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                self.device_info[key] = value
        
        # Update current device identifiers
        serial = self.device_info.get('SerialNumber', 'N/A')
        if serial == 'N/A' and 'UniqueDeviceID' in self.device_info:
            serial = self.device_info['UniqueDeviceID'][-8:]
        
        self.current_serial = serial
        self.current_product_type = self.device_info.get('ProductType', 'N/A')
    
    def is_device_connected(self):
        """Check if device is connected"""
        try:
            ideviceinfo_path = get_lib_path('ideviceinfo.exe')
            if os.path.exists(ideviceinfo_path):
                result = run_subprocess_no_console([ideviceinfo_path], timeout=5)
                return result and result.returncode == 0 and result.stdout.strip()
            return False
        except:
            return False
    
    def get_activation_state(self):
        """Get device activation state"""
        try:
            ideviceinfo_path = get_lib_path('ideviceinfo.exe')
            if not os.path.exists(ideviceinfo_path):
                return "Unknown"
                
            result = run_subprocess_no_console([ideviceinfo_path, '-k', 'ActivationState'], timeout=15)
            if result and result.returncode == 0:
                return result.stdout.strip()
            return "Unknown"
        except Exception as e:
            print(f"Error getting activation state: {e}")
            return "Unknown"
    
    def get_model_name(self):
        """Get friendly device model name"""
        product_type = self.current_product_type
        if not product_type or product_type == "N/A":
            return "Unknown"
        
        # Check cache
        if product_type in self.cached_models:
            return self.cached_models[product_type]
        
        # Get friendly name
        model_name = self._get_friendly_model_name(product_type)
        self.cached_models[product_type] = model_name
        return model_name
    
    def _get_friendly_model_name(self, product_type):
        """Convert product type to friendly name"""
        # Try HardwareModel first
        if self.device_info:
            hardware_model = self.device_info.get('HardwareModel')
            if hardware_model and hardware_model != 'N/A':
                friendly = self._get_name_from_hardware(hardware_model)
                if friendly:
                    return friendly
        
        # Fallback to ProductType mapping
        return self._get_name_from_product_type(product_type)
    
    def _get_name_from_hardware(self, hardware_model):
        """Map hardware model to friendly name"""
        hardware_map = {
            'J217AP': 'iPad Air (3rd gen)', 'J218AP': 'iPad Air (3rd gen)',
            'J171AP': 'iPad (8th gen)', 'J172AP': 'iPad (8th gen)',
            'J181AP': 'iPad (9th gen)', 'J182AP': 'iPad (9th gen)',
            'J307AP': 'iPad Air (4th gen)', 'J308AP': 'iPad Air (4th gen)',
            'J407AP': 'iPad Air (5th gen)', 'J408AP': 'iPad Air (5th gen)',
            'N104AP': 'iPhone 11',
            'D421AP': 'iPhone 11 Pro', 'D431AP': 'iPhone 11 Pro Max',
            'D52GAP': 'iPhone 12 mini', 'D53GAP': 'iPhone 12',
            'D53PAP': 'iPhone 12 Pro', 'D54PAP': 'iPhone 12 Pro Max',
            'D16AP': 'iPhone 13 mini', 'D17AP': 'iPhone 13',
            'D63AP': 'iPhone 13 Pro', 'D64AP': 'iPhone 13 Pro Max',
            'D27AP': 'iPhone 14', 'D28AP': 'iPhone 14 Plus',
            'D73AP': 'iPhone 14 Pro', 'D74AP': 'iPhone 14 Pro Max',
        }
        return hardware_map.get(hardware_model)
    
    def _get_name_from_product_type(self, product_type):
        """Map ProductType to friendly name"""
        product_map = {
            'iPad11,3': 'iPad Air (3rd gen)', 'iPad11,4': 'iPad Air (3rd gen)',
            'iPad11,6': 'iPad (8th gen)', 'iPad11,7': 'iPad (8th gen)',
            'iPad12,1': 'iPad (9th gen)', 'iPad12,2': 'iPad (9th gen)',
            'iPad13,1': 'iPad Air (4th gen)', 'iPad13,2': 'iPad Air (4th gen)',
            'iPhone12,1': 'iPhone 11',
            'iPhone12,3': 'iPhone 11 Pro', 'iPhone12,5': 'iPhone 11 Pro Max',
            'iPhone13,1': 'iPhone 12 mini', 'iPhone13,2': 'iPhone 12',
            'iPhone13,3': 'iPhone 12 Pro', 'iPhone13,4': 'iPhone 12 Pro Max',
            'iPhone14,2': 'iPhone 13 Pro', 'iPhone14,3': 'iPhone 13 Pro Max',
            'iPhone14,4': 'iPhone 13 mini', 'iPhone14,5': 'iPhone 13',
            'iPhone14,7': 'iPhone 14', 'iPhone14,8': 'iPhone 14 Plus',
            'iPhone15,2': 'iPhone 14 Pro', 'iPhone15,3': 'iPhone 14 Pro Max',
        }
        return product_map.get(product_type, product_type.replace(",", " "))
    
    def reboot_device(self):
        """Reboot the device"""
        try:
            idevicediagnostics_path = get_lib_path('idevicediagnostics.exe')
            if os.path.exists(idevicediagnostics_path):
                result = run_subprocess_no_console([idevicediagnostics_path, 'restart'], timeout=30)
                return result and result.returncode == 0
            return False
        except Exception as e:
            print(f"Error rebooting device: {e}")
            return False
    
    def extract_guid_from_syslog(self):
        """Extract GUID from device syslog"""
        # This is a placeholder - implement actual GUID extraction
        return None
