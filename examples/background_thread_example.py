"""PyQt5 example demonstrating use of a worker thread for long tasks."""

from __future__ import annotations

import sys
import time
from typing import Dict

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class Worker(QObject):
    """Execute a long-running task in a background thread."""

    progress_update = pyqtSignal(int)
    task_finished = pyqtSignal(dict)
    finished = pyqtSignal()

    @pyqtSlot(str)
    def perform_task(self, name: str) -> None:
        """Simulate heavy work.

        Parameters
        ----------
        name: str
            Arbitrary string parameter used in the final result.
        """
        if not name:
            return

        for step in range(1, 6):
            time.sleep(1)
            self.progress_update.emit(step * 20)
        self.task_finished.emit({"greeting": f"Hello, {name}!"})
        self.finished.emit()


class MainWindow(QMainWindow):
    """Main application window managing UI and the worker thread."""

    request_heavy_task = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Background Worker Demo")
        self._setup_ui()
        self._setup_worker_thread()

    def _setup_ui(self) -> None:
        self.start_button = QPushButton("Start Task")
        self.status_label = QLabel("Idle")
        self.progress_bar = QProgressBar()

        layout = QVBoxLayout()
        layout.addWidget(self.start_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.start_button.clicked.connect(self.start_task)

    def _setup_worker_thread(self) -> None:
        """Create the QThread and Worker objects and wire up signals."""
        self.thread = QThread()
        self.worker = Worker()

        # Move the worker object to the newly created thread.
        self.worker.moveToThread(self.thread)

        # Optional initial connection when the thread starts.
        self.thread.started.connect(lambda: self.worker.perform_task(""))

        # Allow the UI to request work from the worker.
        self.request_heavy_task.connect(self.worker.perform_task)

        # Update UI based on worker signals.
        self.worker.progress_update.connect(self.update_progress)
        self.worker.task_finished.connect(self.display_result)

        # Clean up once the worker signals it's done.
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        # Start the thread so it's ready to receive tasks.
        self.thread.start()

    @pyqtSlot()
    def start_task(self) -> None:
        """Handle button click and request work from the worker."""
        self.status_label.setText("Working...")
        self.progress_bar.setValue(0)
        self.request_heavy_task.emit("World")

    @pyqtSlot(int)
    def update_progress(self, value: int) -> None:
        self.progress_bar.setValue(value)

    @pyqtSlot(dict)
    def display_result(self, data: Dict[str, str]) -> None:
        self.status_label.setText(data.get("greeting", "Done"))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
