"""Minimal stub of PyQt5 for headless test environments."""
from types import ModuleType

QtWidgets = ModuleType('PyQt5.QtWidgets')
QtCore = ModuleType('PyQt5.QtCore')

class QApplication:
    def __init__(self, *args, **kwargs):
        pass
    def exec_(self):
        pass
    @staticmethod
    def instance():
        return None

class QMainWindow:
    def __init__(self, *args, **kwargs):
        pass
    def show(self):
        pass
    def isVisible(self):
        return False

class QEventLoop:
    def __init__(self, *args, **kwargs):
        pass
    def exec_(self):
        pass
    def quit(self):
        pass

class QThread:
    def __init__(self, *args, **kwargs):
        pass
    def start(self):
        pass
    def run(self):
        pass
    def quit(self):
        pass
    def wait(self, msecs=0):
        pass

QtWidgets.QApplication = QApplication
QtWidgets.QMainWindow = QMainWindow
QtCore.QEventLoop = QEventLoop
QtCore.QThread = QThread

import sys
sys.modules[__name__ + '.QtWidgets'] = QtWidgets
sys.modules[__name__ + '.QtCore'] = QtCore
