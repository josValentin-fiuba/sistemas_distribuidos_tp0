from socket import *

def recv_all(skt, n):
    """
    Receive exactly `n` bytes from the socket `skt`.

    If the peer closes the connection or an error occurs before `size` bytes are received, 
    a ConnectionError is raised.
    """
    data = b''
    while len(data) < n:
        pkt = skt.recv(n - len(data))
        if not pkt:
            raise ConnectionError("Socket connection closed")
        data += pkt
    return data