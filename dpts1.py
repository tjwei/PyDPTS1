"DPT-S1 screen viewer API"
import asyncio
import socket
from io import BytesIO

import numpy as np
from PIL import Image

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

def read_img(addr, croping=((0,0,0,0), (0,0,0,0)) ):
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
        h1,h2,w1,w2 = croping[0]
        h2 += im.shape[0]
        w2 += im.shape[1]
        im = im[h1:h2, w1:w2, :]
    else:
        h1,h2,w1,w2 = croping[1]
        h2 += im.shape[0]
        w2 += im.shape[1]
        im = im[h1:h2, w1:w2, :]
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
