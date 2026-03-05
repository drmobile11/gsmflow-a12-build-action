# -*- coding: utf-8 -*-
import sys
from PyQt5 import QtCore, QtGui, QtWidgets


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Professional Device Utility")
        self.resize(950, 680)
        self.setMinimumSize(850, 600)

        self.setStyleSheet("""
        QMainWindow {
            background-color: #0e1116;
            color: #e2e8f0;
            font-family: "Segoe UI Variable", "Segoe UI", Arial, sans-serif;
            font-size: 12px;
        }

        QFrame#deviceCard {
            background: #111827;
            border-radius: 18px;
        }

        QLabel {
            color: #cbd5e1;
        }

        QLabel.fieldLabel {
            color: #94a3b8;
            font-weight: 600;
        }

        QLabel.valueLabel {
            background: #1f2937;
            border-radius: 10px;
            padding: 8px 14px;
            font-weight: 600;
            color: #f1f5f9;
        }

        QLabel#statusValue {
            background: #dc2626;
            border-radius: 10px;
            padding: 8px 14px;
            font-weight: 600;
            color: white;
        }

        QProgressBar {
            background: #1f2937;
            border-radius: 4px;
            height: 6px;
        }

        QProgressBar::chunk {
            background-color: #2563eb;
            border-radius: 4px;
        }

        QPushButton {
            border-radius: 16px;
            font-size: 13px;
            font-weight: 600;
            padding: 10px;
        }

        QPushButton:disabled {
            background: #1f2937;
            color: #64748b;
        }

        QPushButton:enabled {
            background: #10b981;
            color: white;
        }

        QPushButton:hover:enabled {
            background: #0ea5a4;
        }

        QPushButton:pressed {
            background: #059669;
        }

        QGroupBox {
            border: 1px solid #1f2937;
            border-radius: 14px;
            background: #0f172a;
        }

        QGroupBox::title {
            color: #94a3b8;
            padding-left: 8px;
        }

        QTextEdit {
            background: #020617;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 10px;
            font-family: "JetBrains Mono", Consolas;
            font-size: 9pt;
            color: #cbd5f5;
        }
        """)

        self.init_ui()

    def init_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        main_layout = QtWidgets.QHBoxLayout(central)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # LEFT SIDE
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.setSpacing(18)

        # Device Card
        self.device_card = QtWidgets.QFrame(objectName="deviceCard")
        card_layout = QtWidgets.QVBoxLayout(self.device_card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(14)

        title = QtWidgets.QLabel("CONNECTED DEVICE")
        title.setStyleSheet("color:#64748b; font-size:11px; letter-spacing:2px;")
        card_layout.addWidget(title)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(12)

        self.model = self.create_row(grid, 0, "Model")
        self.serial = self.create_row(grid, 1, "Serial")
        self.version = self.create_row(grid, 2, "Version")
        self.identifier = self.create_row(grid, 3, "Identifier")

        status_label = QtWidgets.QLabel("Status")
        status_label.setProperty("class", "fieldLabel")
        grid.addWidget(status_label, 4, 0)

        self.status = QtWidgets.QLabel("Disconnected", objectName="statusValue")
        grid.addWidget(self.status, 4, 1)

        card_layout.addLayout(grid)
        left_layout.addWidget(self.device_card)

        # Progress
        self.progress = QtWidgets.QProgressBar()
        self.progress.setVisible(False)
        left_layout.addWidget(self.progress)

        # Action Button
        self.action_btn = QtWidgets.QPushButton("START PROCESS")
        self.action_btn.clicked.connect(self.simulate_process)
        left_layout.addWidget(self.action_btn)

        left_layout.addStretch()
        main_layout.addLayout(left_layout)

        # RIGHT SIDE LOG
        self.log_group = QtWidgets.QGroupBox("Activity Log")
        log_layout = QtWidgets.QVBoxLayout(self.log_group)

        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        log_layout.addWidget(self.log)

        main_layout.addWidget(self.log_group)

    def create_row(self, grid, row, label_text):
        label = QtWidgets.QLabel(label_text)
        label.setProperty("class", "fieldLabel")
        grid.addWidget(label, row, 0)

        value = QtWidgets.QLabel("N/A")
        value.setProperty("class", "valueLabel")
        grid.addWidget(value, row, 1)
        return value

    def simulate_process(self):
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status.setText("Processing...")
        self.status.setStyleSheet("background:#f59e0b; border-radius:10px; padding:8px 14px; color:white;")

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(80)

    def update_progress(self):
        value = self.progress.value() + 2
        self.progress.setValue(value)
        self.log.append(f"Processing step... {value}%")

        if value >= 100:
            self.timer.stop()
            self.status.setText("Completed")
            self.status.setStyleSheet("background:#10b981; border-radius:10px; padding:8px 14px; color:white;")
            self.log.append("Process completed successfully.")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())