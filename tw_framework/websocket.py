"""Minimal RFC 6455 WebSocket implementation, stdlib-only (no external deps).

Handles the HTTP Upgrade handshake and basic text/binary frame
send/receive over the raw socket owned by an http.server request
handler. Designed for TW's threaded dev/prod server: each connection
runs in its own thread (ThreadingMixIn), so a blocking recv loop here
is fine and does not stall other requests.
"""
import base64
import hashlib
import socket
import struct

WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

OPCODE_CONTINUATION = 0x0
OPCODE_TEXT = 0x1
OPCODE_BINARY = 0x2
OPCODE_CLOSE = 0x8
OPCODE_PING = 0x9
OPCODE_PONG = 0xA


class WebSocketClosed(Exception):
    """Raised internally when the peer closes the connection or the socket errors out."""


def is_websocket_upgrade(headers) -> bool:
    connection = str(headers.get("Connection", "")).lower()
    upgrade = str(headers.get("Upgrade", "")).lower()
    return "upgrade" in connection and upgrade == "websocket"


def _compute_accept_key(client_key: str) -> str:
    sha1 = hashlib.sha1((client_key + WS_MAGIC).encode("utf-8")).digest()
    return base64.b64encode(sha1).decode("ascii")


def perform_handshake(handler) -> bool:
    """Sends the 101 Switching Protocols response directly over the raw socket.
    Returns True on success. `handler` is a BaseHTTPRequestHandler instance."""
    client_key = handler.headers.get("Sec-WebSocket-Key")
    if not client_key:
        return False
    accept_key = _compute_accept_key(client_key)
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept_key}\r\n"
        "\r\n"
    )
    try:
        handler.wfile.write(response.encode("utf-8"))
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False
    return True


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    chunks = []
    remaining = n
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise WebSocketClosed("connection closed while reading")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_frame(sock: socket.socket):
    """Reads one WebSocket frame from the client. Returns (opcode, payload_bytes)."""
    header = _recv_exact(sock, 2)
    b0, b1 = header[0], header[1]
    fin = (b0 & 0x80) != 0
    opcode = b0 & 0x0F
    masked = (b1 & 0x80) != 0
    length = b1 & 0x7F

    if length == 126:
        length = struct.unpack(">H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _recv_exact(sock, 8))[0]

    mask_key = _recv_exact(sock, 4) if masked else b""
    payload = _recv_exact(sock, length) if length else b""
    if masked:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

    return opcode, payload, fin


def _encode_frame(opcode: int, payload: bytes) -> bytes:
    header = bytearray()
    header.append(0x80 | opcode)
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header += struct.pack(">H", length)
    else:
        header.append(127)
        header += struct.pack(">Q", length)
    return bytes(header) + payload


class WebSocketConnection:
    """A single upgraded connection. One instance per client; runs on its
    own request-handler thread."""

    def __init__(self, sock: socket.socket, path: str, headers=None):
        self.sock = sock
        self.path = path
        self.headers = headers or {}
        self.closed = False

    def send_text(self, message: str) -> None:
        if self.closed:
            return
        try:
            self.sock.sendall(_encode_frame(OPCODE_TEXT, message.encode("utf-8")))
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.closed = True

    def send_bytes(self, data: bytes) -> None:
        if self.closed:
            return
        try:
            self.sock.sendall(_encode_frame(OPCODE_BINARY, data))
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.closed = True

    def close(self, code: int = 1000) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.sock.sendall(_encode_frame(OPCODE_CLOSE, struct.pack(">H", code)))
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _pong(self, payload: bytes) -> None:
        try:
            self.sock.sendall(_encode_frame(OPCODE_PONG, payload))
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.closed = True

    def __iter__(self):
        """Yields text (str) or binary (bytes) messages until the client
        disconnects. Ping/pong and close frames are handled transparently."""
        buffer = bytearray()
        buffer_opcode = None
        while not self.closed:
            try:
                opcode, payload, fin = _read_frame(self.sock)
            except (WebSocketClosed, ConnectionResetError, OSError, struct.error):
                self.closed = True
                return

            if opcode == OPCODE_CLOSE:
                self.closed = True
                return
            if opcode == OPCODE_PING:
                self._pong(payload)
                continue
            if opcode == OPCODE_PONG:
                continue

            if opcode in (OPCODE_TEXT, OPCODE_BINARY):
                buffer_opcode = opcode
                buffer = bytearray(payload)
            elif opcode == OPCODE_CONTINUATION:
                buffer.extend(payload)
            else:
                continue

            if fin and buffer_opcode is not None:
                if buffer_opcode == OPCODE_TEXT:
                    try:
                        yield buffer.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                else:
                    yield bytes(buffer)
                buffer = bytearray()
                buffer_opcode = None
