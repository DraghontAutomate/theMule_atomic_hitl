import os
import sys

from PyQt5.QtCore import QObject, pyqtSlot, QUrl
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import QApplication


class Backend(QObject):
    @pyqtSlot(str)
    def on_message(self, message):
        print(f"Message from JS: {message}")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    view = QWebEngineView()
    channel = QWebChannel()
    backend = Backend()
    channel.registerObject("backend", backend)
    view.page().setWebChannel(channel)

    file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "index.html"))
    view.setUrl(QUrl.fromLocalFile(file_path))
    view.show()

    sys.exit(app.exec_())
