"""Adquisicion: cliente TCP con timeout, buffer acotado y reconexion gestionada por el orquestador."""
import socket

MAX_BUFFER = 65536


class FrameTooLarge(ValueError):
    pass


class Acquirer:
    def __init__(self, host, port, timeout=1.0):
        self.host, self.port, self.timeout = host, port, timeout
        self.sock = None
        self.buf = b""

    @property
    def connected(self):
        return self.sock is not None

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)
        self.buf = b""

    def read_line(self) -> bytes:
        while b"\n" not in self.buf:
            chunk = self.sock.recv(4096)  # socket.timeout se propaga al orquestador
            if not chunk:
                raise ConnectionError("el dispositivo cerro la conexion")
            self.buf += chunk
            if len(self.buf) > MAX_BUFFER and b"\n" not in self.buf:
                self.buf = b""
                raise FrameTooLarge("buffer excedido sin fin de trama")
        line, _, self.buf = self.buf.partition(b"\n")
        return line

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock, self.buf = None, b""
