import os
from PyQt5.QtWidgets import QDialog
from PyQt5 import uic

class SetupInstructionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), "SetupInstructionDialogUI.ui")
        uic.loadUi(ui_path, self)

        # Connect buttons
        self.btnCancel.clicked.connect(self.reject)
        self.btnContinue.clicked.connect(self.accept)

class CustomMessageBox(QDialog):
    def __init__(self, title, message, serial_number, parent=None):
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), "CustomMessageBoxUI.ui")
        uic.loadUi(ui_path, self)

        # Set data
        self.labelTitle.setText(title)
        self.labelMessage.setText(message)
        self.labelSerial.setText(f"Serial: {serial_number}")

        # Connect buttons
        self.btnCancel.clicked.connect(self.reject)
        self.btnProceed.clicked.connect(self.accept)

class ActivationResultDialog(QDialog):
    def __init__(self, title, message, is_success=True, parent=None):
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), "ActivationResultDialogUI.ui")
        uic.loadUi(ui_path, self)

        # Set fields
        self.labelTitle.setText(title)
        self.labelMessage.setText(message)

        # Success or failure styling
        if is_success:
            # Green for success
            self.labelIcon.setText("✅")
            self.labelTitle.setStyleSheet("""
                font-size: 26px;
                font-weight: bold;
                color: #10b981;
            """)
            self.labelInfo.setVisible(False)
        else:
            # Red for failure
            self.labelIcon.setText("❌")
            self.labelTitle.setStyleSheet("""
                font-size: 26px;
                font-weight: bold;
                color: #ef4444;
            """)
            self.labelInfo.setVisible(True)

        # Connect button
        self.btnOk.clicked.connect(self.accept)
