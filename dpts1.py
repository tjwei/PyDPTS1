"DPT-S1 screen viewer"
import asyncio
import ctypes
import queue
import socket
import subprocess
import sys
from io import BytesIO
from time import sleep

import numpy as np
from PIL import Image
from PyQt5 import QtCore
from PyQt5.QtCore import QEvent, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QImage, QPainter
from PyQt5.QtWidgets import QApplication, QWidget


def read_data(addr):
    "read data from DPT-S1"
    conn = socket.create_connection((addr, 54321))
    try:
        with conn.makefile("rb") as f:
            data = f.read()
    except:
        data = b""
    conn.close()
    return data

END_TAG = b"</command>\n"

def read_img(addr):
    "read screen image from DPT-S1"
    b = read_data(addr)
    end_loc = b.find(END_TAG) + len(END_TAG)
    if end_loc < 0:
        return None
    head = b[:end_loc]
    if b'RETSCREENSYNC' not in head:
        return None
    data = b[end_loc:]
    bio = BytesIO(data)
    im = Image.open(bio)
    im = np.array(im)
    if b'portrait' in head:
        im = im[150:-100, 68:, :]
    else:
        im = im[68:, 20:-95, :]
        im = im[:, ::-1, :].swapaxes(0, 1)

    return im.copy()

def find_device_ip():
    "Find ip of DPT-S1"
    loop = asyncio.get_event_loop()
    async def scanner(ip):
        try:
            fut = asyncio.open_connection(ip, 54321, loop=loop)
            await asyncio.wait_for(fut, timeout=0.5)
            return ip
        except (OSError, asyncio.TimeoutError):
            return ""
    tasks = asyncio.wait([scanner("203.0.113.%d"%i) for i in range(1,256)])
    results = loop.run_until_complete(tasks)
    loop.close()
    ip = max(t.result() for t in results[0])
    return ip

class Thread(QtCore.QThread):
    trigger = QtCore.pyqtSignal(int)
    def __init__(self, ip, img_queue):
        self.ip = ip
        QtCore.QThread.__init__(self)
        self.img_queue = img_queue
    def timer_func(self):
        if not self.img_queue.empty():
            return
        img = read_img(self.ip)
        if img is not None:
            self.img_queue.put(img)
            self.trigger.emit(0)
    def run(self):
        timer = QtCore.QTimer()
        timer.timeout.connect(self.timer_func)
        timer.start(1000)
        self.exec_()

class ScreenViewer(QWidget):
    "main widget"
    def __init__(self, img_queue):
        super().__init__()
        self.initUI()
        self.img_queue = img_queue

    def initUI(self):
        self.setWindowTitle('DPT-S1 viewer')
        self.setStyleSheet("background-color: #f8fdf7;")
        self.showFullScreen()
        self.img = None
        # attempt to disable screen saver
        # winid_ptr = self.winId()
        # ctypes.pythonapi.PyCapsule_GetPointer.restype = ctypes.c_void_p
        # ctypes.pythonapi.PyCapsule_GetPointer.argtypes = [ctypes.py_object, ctypes.c_char_p]
        # winid = ctypes.pythonapi.PyCapsule_GetPointer(winid_ptr.ascapsule(), None)
        # subprocess.call(['xdg-screensaver', 'suspend', str(winid)])

    def paintEvent(self, event):
        try:
            self.img = im = self.img_queue.get_nowait()
        except queue.Empty:
            im = self.img
        qp = QPainter()
        qp.begin(self)
        if im is not None:
            qimg = QImage(im.data, im.shape[1], im.shape[0], im.strides[0], QImage.Format_RGB888)
            w, h = self.width(), self.height()
            iw, ih = qimg.width(), qimg.height()
            if w/h < iw/ih:
                h2 = ih*w/iw
                rect = QRectF(0, (h-h2)/2, w, h2)
            else:
                w2 = iw * h / ih
                rect = QRectF((w-w2)/2, 0, w2, h)
            qp.drawImage(rect, qimg)
        qp.end()
        # attempt to disable screen saver
        #kevent = QKeyEvent(QEvent.KeyPress, Qt.Key_Enter, Qt.NoModifier)
        #QApplication.postEvent(self, kevent)
        #kevent = QKeyEvent(QEvent.KeyRelease, Qt.Key_Enter, Qt.NoModifier)
        #QApplication.postEvent(self, kevent)

def main():
    ip = find_device_ip()
    if ip == "":
        print("cannot find the device")
        sys.exit(-1)
    print("ip="+ip)
    img_queue = queue.Queue()
    app = QApplication(sys.argv)
    thread_instance = Thread(ip, img_queue)
    thread_instance.start()
    viewer = ScreenViewer(img_queue)
    thread_instance.trigger.connect(viewer.repaint)
    app.exec_()
    thread_instance.exit()
if __name__ == '__main__':
    main()
