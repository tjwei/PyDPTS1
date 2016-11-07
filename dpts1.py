"DPT-S1 screen viewer"
import asyncio
import socket
import sys
from io import BytesIO
from time import sleep

import numpy as np
from PIL import Image
from PyQt5 import QtCore
from PyQt5.QtCore import QRectF, Qt
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



end_tag = b"</command>\n"

def read_img(addr):
    "read screen image from DPT-S1"
    b = read_data(addr)
    end_loc = b.find(end_tag) + len(end_tag)
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
        im = im[150:-100, 66:, :]
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
    def __init__(self, ip):
        self.ip = ip
        QtCore.QThread.__init__(self)
    def timer_func(self):
        global nimg
        img = read_img(self.ip)
        if img is not None:
            nimg = img
            self.trigger.emit(0)
    def run(self):
        print("Thread works")
        timer = QtCore.QTimer()
        timer.timeout.connect(self.timer_func)
        timer.start(1000)
        self.exec_()

class ScreenViewer(QWidget):
    "main widget"
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.text = '一二三四五'
        self.setWindowTitle('Draw text')
        self.setStyleSheet("background-color:black;")
        self.setWindowOpacity(0.1)
        self.showFullScreen()

    def paintEvent(self, event):
        qp = QPainter()
        im = nimg
        qimg = QImage(im.data, im.shape[1], im.shape[0], im.strides[0], QImage.Format_RGB888)
        w, h = self.width(), self.height()
        iw, ih = qimg.width(), qimg.height()
        if w/h < iw/ih:
            h2 = ih*w/iw
            rect = QRectF(0, (h-h2)/2, w, h2)
        else:
            w2 = iw * h / ih
            rect = QRectF((w-w2)/2, 0, w2, h)
        qp.begin(self)
        qp.drawImage(rect, qimg)
        qp.end()


def main():
    ip = find_device_ip()
    if ip == "":
        print("cannot find the device")
        sys.exit(-1)
    print("ip="+ip)
    nimg = read_img(ip)
    if nimg is None:
        sys.exit(1)
    app = QApplication(sys.argv)
    thread_instance = Thread(ip)
    thread_instance.start()
    viewer = ScreenViewer()
    thread_instance.trigger.connect(viewer.repaint)
    app.exec_()
    thread_instance.exit()
if __name__ == '__main__':
    main()
