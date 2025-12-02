"""RCON client for checking Factorio server readiness."""
import socket
import struct
import logging

logger = logging.getLogger(__name__)

# RCON Protocol constants
SERVERDATA_AUTH = 3
SERVERDATA_AUTH_RESPONSE = 2
SERVERDATA_EXECCOMMAND = 2
SERVERDATA_RESPONSE_VALUE = 0


class RCONError(Exception):
    """RCON connection or protocol error"""
    pass


def check_rcon_ready(host: str, port: int = 27015, password: str = None, timeout: int = 5) -> bool:
    """
    Check if Factorio RCON server is ready by attempting to connect and authenticate.

    Args:
        host: Server IP address
        port: RCON port (default 27015)
        password: RCON password (if None, uses placeholder)
        timeout: Connection timeout in seconds

    Returns:
        True if RCON is accessible and responding, False otherwise
    """
    if password is None:
        password = "changeme-generate-secure-password"

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            # Try to authenticate
            request_id = 1
            _send_packet(sock, request_id, SERVERDATA_AUTH, password)

            # Read auth response
            response_id, response_type, _ = _receive_packet(sock)

            # Successful auth means server is ready
            if response_type == SERVERDATA_AUTH_RESPONSE and response_id == request_id:
                logger.info(f"RCON connection successful to {host}:{port}")
                return True
            else:
                logger.warning(f"RCON auth failed to {host}:{port}")
                return False

    except socket.timeout:
        logger.debug(f"RCON connection timeout to {host}:{port}")
        return False
    except ConnectionRefusedError:
        logger.debug(f"RCON connection refused to {host}:{port} (server not ready yet)")
        return False
    except Exception as e:
        logger.debug(f"RCON check failed for {host}:{port}: {e}")
        return False


def _send_packet(sock: socket.socket, request_id: int, packet_type: int, body: str):
    """Send an RCON packet."""
    body_bytes = body.encode('utf-8') + b'\x00\x00'
    size = len(body_bytes) + 10  # 4 (id) + 4 (type) + body + 2 (null terminators)

    packet = struct.pack('<iii', size - 4, request_id, packet_type) + body_bytes
    sock.sendall(packet)


def _receive_packet(sock: socket.socket) -> tuple:
    """Receive an RCON packet and return (id, type, body)."""
    # Read packet size
    size_data = sock.recv(4)
    if len(size_data) < 4:
        raise RCONError("Incomplete packet size")

    size = struct.unpack('<i', size_data)[0]

    # Read rest of packet
    data = b''
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise RCONError("Connection closed while reading packet")
        data += chunk

    # Parse packet
    request_id, packet_type = struct.unpack('<ii', data[:8])
    body = data[8:-2].decode('utf-8', errors='ignore')

    return request_id, packet_type, body
