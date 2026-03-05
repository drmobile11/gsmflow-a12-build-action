import requests
from config import SERVER_URL, API_BASE_URL, REGISTER_URL, ACTIVATE_URL

class Api:
    """Server API Client - All operations through local server"""
    
    @staticmethod
    def register_device(sn, prd):
        """Register a new device with the server"""
        try:
            payload = {"sn": sn, "prd": prd}
            response = requests.post(REGISTER_URL, json=payload, timeout=15)
            return response.json()
        except requests.exceptions.Timeout:
            return {"success": False, "error": "timeout"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "connection_error"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_device_status(sn):
        """Get device status from server"""
        try:
            response = requests.get(f"{API_BASE_URL}/device/{sn}", timeout=10)
            return response.json()
        except requests.exceptions.Timeout:
            return {"success": False, "error": "timeout"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "connection_error"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def activate_device(sn, prd, guid):
        """Activate device and get all stage URLs from server"""
        try:
            payload = {"sn": sn, "prd": prd, "guid": guid}
            response = requests.post(ACTIVATE_URL, json=payload, timeout=60)
            return response.json()
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Server timeout - activation may take longer. Please wait and try again."}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Cannot connect to server. Please check your internet connection."}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_session_status(session_id):
        """Get session status"""
        try:
            response = requests.get(f"{API_BASE_URL}/session/{session_id}", timeout=5)
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def download_file(url):
        """Download file from server URL"""
        try:
            response = requests.get(url, timeout=60)
            if response.status_code == 200:
                return response.content
            return None
        except requests.exceptions.Timeout:
            print(f"Download timeout: {url}")
            return None
        except requests.exceptions.ConnectionError:
            print(f"Connection error: {url}")
            return None
        except Exception as e:
            print(f"Download error: {e}")
            return None