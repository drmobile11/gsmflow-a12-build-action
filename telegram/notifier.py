# telegram/notifier.py
# DEPRECATED: All Telegram notifications now handled by server
# Use core.api.Api.send_notification() instead

class TelegramNotifier:
    """Deprecated - Use server API for notifications"""
    
    def send_message(self, text):
        """Deprecated - Use Api.send_notification()"""
        pass

    def send_activation_success(self, model, serial, imei):
        """Deprecated - Use Api.send_notification()"""
        pass

    def send_activation_failed(self, model, serial, imei, reason):
        """Deprecated - Use Api.send_notification()"""
        pass

telegram_notifier = TelegramNotifier()