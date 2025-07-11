"""
TFTPy is a simple implementation of the TFTP protocol that can be used to
 transfer files between a client and a server.

This module is a common repository for the TFTP client and server
 implementations.

It handles all TFTP protocol details, such as packet formatting, error handling,
 and file transfer logic.
 
It is not intended to be run directly, but rather imported by the client and
 server modules.

Successfully tested on the following platforms:
    - Windows 10 22H2 with Python 3.12.1
    - Linux Mint 21.2 with Python 3.12.1

Libraries used (all from Python's standard library):
    re
    os
    time
    struct
    socket
    string
    tempfile
    locale
    subprocess
    ipaddress
    enum
    socket

A virtual environment (.venv) was used to isolate the project.

(c) 2025 Pedro Dores, Pedro Vieira, based on code by João Galamba

Submission date: 2025/07/11

Source code licensed under GPLv3. Please refer to:
    https://www.gnu.org/licenses/gpl-3.0.en.html
"""

import re
import os
import time
import struct
import socket
import string
import tempfile
import locale
import subprocess
import ipaddress
from enum import Enum
from socket import socket, AF_INET, SOCK_DGRAM

# ##############################################################################
#
# PROTOCOL CONSTANTS AND TYPES
#
# ##############################################################################

MAX_DATA_LEN = 512       # in bytes
DEFAULT_MODE = "octet"   # transfer mode (one of 'octet', 'netascii', 'mail')
MAX_RETRIES = 5          # number of retries for a request before giving up
INACTIVITY_TIMEOUT = 20  # Não encontro no vídeo do professor Galamba
DEFAULT_BUFFER_SIZE = 8192

# TFTP message opcodes
# https://datatracker.ietf.org/doc/html/rfc1350
# https://datatracker.ietf.org/doc/html/rfc2347 for options negotiation (OACK)
# this last one won't be implemented in this exercise..
class TFTPOpcode(Enum):
    RRQ   = 1   # Read request
    WRQ   = 2   # Write request
    DATA  = 3   # Data transfer
    ACK   = 4   # Acknowledge
    ERROR = 5   # Error packet; What the server responds if a read/write can't
                # be processed, read and write errors during file transmission
                # also cause this message to be sent, and transmission is then
                # terminated. The error number gives a numeric error code,
                # followed by an ASCII error message that might contain
                # additional, operating system-specific information.
    OACK  = 6   # Option Acknowledge; Sent by the server in response to a
                # request for options negotiation, indicating the options
                # accepted by the server. This is used to negotiate options
                # like block size, timeout, and transfer mode before the actual
                # data transfer begins.
#:


# ##############################################################################
#
# ERROR AND EXCEPTIONS
#
# ##############################################################################

class TFTPError(Enum):
    NOT_DEFINED         = (0, "Not defined, see error message (if any).")
    FILE_NOT_FOUND      = (1, "File not found.")
    ACCESS_VIOLATION    = (2, "Access violation.")
    DISK_FULL           = (3, "Disk full or allocation exceeded.")
    ILLEGAL_OPERATION   = (4, "Illegal TFTP operation.")
    UNKNOWN_TRANSFER_ID = (5, "Unknown transfer ID.")
    FILE_EXISTS         = (6, "File already exists.")
    NO_SUCH_USER        = (7, "No such user.")
#:

INET4Address = tuple[str, int]  # TCP/UDP address => IPv4 and port


# ##############################################################################
#
# SERVER SEND AND RECEIVE FILES, SEND DIR
#
# ##############################################################################

def server_send_dir(transfer_sock, client_addr, server_dir):
    """
    Sends the local directory listing to the client, responding to a dir request
    """
    if os.name == 'nt':
        cmd = f'dir "{server_dir}"'
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        raw_listing = proc.stdout.read()
        
        raw_listing = raw_listing.replace(b'\xa0', b' ')
        encoding = locale.getpreferredencoding()
        listing = raw_listing.decode(encoding, errors='replace')
    else:
        cmd = f'ls -lh "{server_dir}"'
        listing = os.popen(cmd).read()

    with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8') as tmp:
        tmp.write(listing)
        tmp_filename = tmp.name

    print(f"[{time.strftime('%H:%M:%S')}] DIR request from {client_addr} for '{server_dir}'")

    server_send_file(transfer_sock, client_addr, tmp_filename, "dir_listing.txt")

    try:
        os.remove(tmp_filename)
    except Exception as e:
        print(f"Could not remove temp file: {e}")
#:


def server_send_file(transfer_sock, client_addr, local_file, remote_file):
    """
    Sends the requested 'local_file' to the client, in TFTP blocks of 512 bytes.
    """
    print(f"[{time.strftime('%H:%M:%S')}] RRQ request from {client_addr} for '{remote_file}'")
    with open(local_file, 'rb') as f:
        block_number = 1
        while True:
            data_block = f.read(MAX_DATA_LEN)
            dat_packet = pack_dat(block_number, data_block)
            for attempt in range(MAX_RETRIES):
                transfer_sock.sendto(dat_packet, client_addr)
                try:
                    transfer_sock.settimeout(INACTIVITY_TIMEOUT)
                    packet, _ = transfer_sock.recvfrom(DEFAULT_BUFFER_SIZE)
                except TimeoutError:
                    print(f"Timeout waiting for ACK for block {block_number} (attempt {attempt+1}) from {client_addr}. Retrying...")
                    continue
                except Exception as e:
                    print(f"Error during RRQ transfer: {e}")
                    return

                op = unpack_opcode(packet)
                if op == TFTPOpcode.ACK:
                    ack_block = unpack_ack(packet)
                    if ack_block == block_number:
                        break
                    else:
                        print(f"Invalid ACK block number: {ack_block} (expected {block_number})")
                        continue
                elif op == TFTPOpcode.ERROR:
                    err_code, err_msg = unpack_err(packet)
                    print(f"TFTP error from client: {err_code} {err_msg}")
                    return
                else:
                    print(f"Invalid packet opcode: {op}. Expecting ACK.")
                    continue
            else:
                print(f"Max retries reached for block {block_number}. Aborting transfer.")
                return

            if len(data_block) < MAX_DATA_LEN:
                break
            block_number = (block_number) % 65535 + 1

    print(f"[{time.strftime('%H:%M:%S')}] Sent file '{remote_file}' to {client_addr}")
#:


def server_receive_file(transfer_sock, client_addr, local_file, remote_file):
    """
    Receives a file from the client, in TFTP blocks of 512 bytes.
    """
    print(f"[{time.strftime('%H:%M:%S')}] WRQ request from {client_addr} for '{remote_file}'")
    success = False
    try:
        with open(local_file, 'wb') as f:
            ack_packet = pack_ack(0)
            transfer_sock.sendto(ack_packet, client_addr)
            next_block_number = 1
            while True:
                try:
                    transfer_sock.settimeout(INACTIVITY_TIMEOUT)
                    packet, _ = transfer_sock.recvfrom(DEFAULT_BUFFER_SIZE)
                except TimeoutError:
                    print(f"Timeout waiting for DATA for block {next_block_number} from {client_addr}. Aborting transfer.")
                    return
                except Exception as e:
                    print(f"Error during WRQ transfer: {e}")
                    return

                op = unpack_opcode(packet)
                if op == TFTPOpcode.DATA:
                    data_block_num, data = unpack_dat(packet)
                    
                    if data_block_num == next_block_number:
                        f.write(data)
                        ack_packet = pack_ack(next_block_number)
                        transfer_sock.sendto(ack_packet, client_addr)
                        if len(data) < MAX_DATA_LEN:
                            success = True
                            break
                        next_block_number += 1
                    elif data_block_num == next_block_number - 1:
                        # Repeated block, lost ACK, just resend the ACK, don't write
                        ack_packet = pack_ack(data_block_num)
                        transfer_sock.sendto(ack_packet, client_addr)
                        # Don't increment next_block_number, don't write
                    else:
                        print(f"Invalid DATA block number: {data_block_num} (expected {next_block_number})")
                        continue  # Wait for correct bblock
                elif op == TFTPOpcode.ERROR:
                    err_code, err_msg = unpack_err(packet)
                    print(f"TFTP error from client: {err_code} {err_msg}")
                    return
                else:
                    print(f"Invalid packet opcode: {op}. Expecting DATA.")
                    continue
    finally:
        if not success and os.path.exists(local_file):
            try:
                os.remove(local_file)
                print(f"Aborted transfer: incomplete file '{remote_file}' removed.")
            except Exception as e:
                print(f"Could not remove incomplete file '{remote_file}': {e}")
    if success:
        print(f"[{time.strftime('%H:%M:%S')}] Received file '{remote_file}' from {client_addr}")
#:


# ##############################################################################
#
# CLIENT SEND AND RECEIVE FILES
#
# ##############################################################################

# GET_FILE e PUT_FILE, alterados, passando de filename para remote_file, local_file
def client_get_file(server_addr: INET4Address, remote_file: str, local_file: str = None):
    """
    Get the remote file given by 'remote_file' thougth a TFTP RRQ
    connection to remote server at 'server_addr'.
    """
    success = False

    if local_file is None:
        local_file = remote_file

    with socket(AF_INET, SOCK_DGRAM) as sock:
        sock.settimeout(INACTIVITY_TIMEOUT)
        try:
            with open(local_file, 'wb') as out_file:
                rqq = pack_rrq(remote_file)
                next_block_number = 1
                sock.sendto(rqq, server_addr)

                while True:
                    packet, server_address = sock.recvfrom(DEFAULT_BUFFER_SIZE)
                    opcode = unpack_opcode(packet)

                    if opcode == TFTPOpcode.DATA:
                        block_number, data = unpack_dat(packet)

                        if block_number == next_block_number:
                            out_file.write(data)
                            next_block_number += 1
                        elif block_number == next_block_number - 1:
                           # Repeated block, lost ACK, just resend the ACK, don't write
                            pass
                        else:
                            error_msg = f'Invalid block number: {block_number}'
                            raise ProtocolError(error_msg)

                        # Send ACK for the received block
                        ack = pack_ack(block_number)
                        sock.sendto(ack, server_address)

                        if len(data) < MAX_DATA_LEN:
                            success = True
                            return block_number * DEFAULT_BUFFER_SIZE + len(data)
                        
                    elif opcode == TFTPOpcode.ERROR:
                        err_code, err_msg = unpack_err(packet)
                        raise Err(err_code, err_msg)

                    else:
                        error_msg = f'Invalid packet opcode: {opcode}. Expecting {TFTPOpcode.DATA=}'
                        raise ProtocolError(error_msg)
        finally:
            if not success and os.path.exists(local_file):
                try:
                    os.remove(local_file)
                    print(f"Aborted transfer: incomplete file '{local_file}' removed.")
                except Exception as e:
                    print(f"Could not remove incomplete file '{local_file}': {e}")
#:


def client_put_file(server_addr: INET4Address, remote_file: str, local_file: str = None):
    if local_file is None:
        local_file = remote_file

    with socket(AF_INET, SOCK_DGRAM) as sock:
        sock.settimeout(INACTIVITY_TIMEOUT)
        with open(local_file, 'rb') as in_file:
            wrq = pack_wrq(remote_file)
            
            for attempt in range(MAX_RETRIES):
                sock.sendto(wrq, server_addr)
                try:
                    packet, server_address = sock.recvfrom(DEFAULT_BUFFER_SIZE)
                except TimeoutError:
                    print(f"Timeout waiting for ACK 0 (attempt {attempt+1}). Retrying WRQ...")
                    continue
                opcode = unpack_opcode(packet)
                if opcode == TFTPOpcode.ACK:
                    block_number = unpack_ack(packet)
                    if block_number == 0:
                        break 
                elif opcode == TFTPOpcode.ERROR:
                    err_code, err_msg = unpack_err(packet)
                    print(f"TFTP error from server: {err_code} {err_msg}")
                    return
            else:
                print("Max retries reached for WRQ. Aborting transfer.")
                return

            next_block_number = 1
            while True:
                data = in_file.read(MAX_DATA_LEN)
                if not data:
                    break  # End of file

                dat_packet = pack_dat(next_block_number, data)
                for attempt in range(MAX_RETRIES):
                    sock.sendto(dat_packet, server_address)
                    try:
                        sock.settimeout(INACTIVITY_TIMEOUT)
                        ack_packet, _ = sock.recvfrom(DEFAULT_BUFFER_SIZE)
                    except TimeoutError:
                        print(f"Timeout waiting for ACK for block {next_block_number} (attempt {attempt+1}). Retrying...")
                        continue
                    ack_opcode = unpack_opcode(ack_packet)
                    if ack_opcode == TFTPOpcode.ACK:
                        ack_block = unpack_ack(ack_packet)
                        if ack_block == next_block_number:
                            break  # ACK correto, prouceed to next block
                        else:
                            print(f"Invalid ACK block number: {ack_block} (expected {next_block_number})")
                            continue
                    elif ack_opcode == TFTPOpcode.ERROR:
                        err_code, err_msg = unpack_err(ack_packet)
                        print(f"TFTP error from server: {err_code} {err_msg}")
                        return
                    else:
                        print(f"Invalid packet opcode: {ack_opcode}. Expecting ACK.")
                        continue
                else:
                    print(f"Max retries reached for block {next_block_number}. Aborting transfer.")
                    return

                next_block_number = (next_block_number) % 65535 + 1

            print(f"File '{local_file}' sent successfully.")
#:


# ##############################################################################
#
# PACKET PACKING AND UNPACKING
#
# ##############################################################################
# Endianness, Big-endian, Little-endian https://en.wikipedia.org/wiki/Endianness
#  Usar '!H' or '>H' em vez de 'H'? Sim, ver página 8 do enunciado.
#  Parte4A_Pacotes.mp4 utiliza 'H' mas o Parte4B_Pacotes.mp4 já utiliza '!H'.
#

def pack_rrq(filename, mode=DEFAULT_MODE) -> bytes:
    return _pack_rq(TFTPOpcode.RRQ, filename, mode)
#:

def pack_wrq(filename, mode=DEFAULT_MODE) -> bytes:
    return _pack_rq(TFTPOpcode.WRQ, filename, mode)
#:

def _pack_rq(opcode: TFTPOpcode, filename, mode=DEFAULT_MODE) -> bytes:
    if not is_ascii_printable(filename):
        raise TFTPValueError(f"Invalid filename: {filename}. Not ASCII printable")

    filename_bytes = filename.encode() + b'\x00'
    mode_bytes = mode.encode() + b'\x00'
    rrq_fmt = f'!H{len(filename_bytes)}s{len(mode_bytes)}s'
    return struct.pack(rrq_fmt, opcode.value, filename_bytes, mode_bytes)
#:


def unpack_rrq(packet: bytes) -> tuple[str, str]:
    return _unpack_rq(TFTPOpcode.RRQ, packet)
#:

def unpack_wrq(packet: bytes) -> tuple[str, str]:
    return _unpack_rq(TFTPOpcode.WRQ, packet)
#:

def _unpack_rq(expected_opcode: TFTPOpcode, packet: bytes) -> tuple[str, str]:
    received_opcode = unpack_opcode(packet)
    if received_opcode.value != expected_opcode.value:
        raise TFTPValueError(f"Invalid opcode: {received_opcode.value}. Expected {expected_opcode.value}")
    delim_pos = packet.index(b'\x00', 2)
    filename = packet[2:delim_pos].decode()
    mode = packet[delim_pos + 1:-1].decode()
    return filename, mode
#:


def unpack_opcode(packet: bytes) -> TFTPOpcode:
    opcode, *_ = struct.unpack('!H', packet[:2])
    # if opcode not in [e.value for e in TFTPOpcode]:           #  Alternativa 1
    # if opcode not in TFTPOpcode._value2member_map_:           #  Alternativa 2
    # if opcode not in TFTPOpcode._value2member_map_.keys():    #  Alternativa 3
    try:                                                        #  Solução mais pythónica
        return TFTPOpcode(opcode)
    except ValueError:
        raise TFTPValueError(f"Invalid opcode: {opcode}")
#:


def pack_dat(block_number: int, data: bytes) -> bytes:
    if len(data) > MAX_DATA_LEN:
        raise TFTPValueError(f"Data length exceeds {MAX_DATA_LEN} bytes")

    # fmt = f'!H{len(data)}s'  Devolve erro. Ver com o original
    fmt = f'!HH{len(data)}s'
    return struct.pack(fmt, TFTPOpcode.DATA.value, block_number, data)
#:


def unpack_dat(packet: bytes) -> tuple[int, bytes]:
    opcode, block_number = struct.unpack('!HH', packet[:4])
    if opcode != TFTPOpcode.DATA.value:
        raise TFTPValueError(f"Invalid opcode: {opcode}")
    return block_number, packet[4:]
#:


def pack_ack(block_number: int) -> bytes:
    return struct.pack('!HH', TFTPOpcode.ACK.value, block_number)
#:

def unpack_ack(packet: bytes) -> int:
    if len(packet) > 4: # Creio que devia ser if len(packet) != 4 VERIFICAR
        raise TFTPValueError(f"Invalid packet length: {len(packet)}")
    return struct.unpack('!H', packet[2:4])[0]
#:


def pack_err(error_num: int, error_msg: str) -> bytes:
    if not is_ascii_printable(error_msg):
        raise TFTPValueError(f"Invalid error message: {error_msg}. Not ASCII printable")

    error_msg_bytes = error_msg.encode() + b'\x00'
    fmt = f'!HH{len(error_msg_bytes)}s'
    return struct.pack(fmt, TFTPOpcode.ERROR.value, error_num, error_msg_bytes)
#:

def unpack_err(packet: bytes) -> tuple[int, str]:
    fmt = f'!HH{len(packet)-4}s'
    opcode, error_num, error_msg = struct.unpack(fmt, packet)
    if opcode != TFTPOpcode.ERROR.value:
        raise TFTPValueError(f"Invalid opcode: {opcode}")
    return error_num, error_msg[:-1].decode()
#:


################################################################################
##
##      ERRORS AND EXCEPTIONS
##
################################################################################

class TFTPValueError(ValueError):
    pass
#:

class NetworkError(Exception):
    """
    Any network error, like "host not found", timeouts, etc.
    """
#:

class ProtocolError(NetworkError):
    """
    A protocol error like unexpected or invalid opcode, wrong block 
    number, or any other invalid protocol parameter.
    """
#:

class Err(Exception):
    """
    An error sent by the server. It may be caused because a read/write 
    can't be processed. Read and write errors during file transmission 
    also cause this message to be sent, and transmission is then 
    terminated. The error number gives a numeric error code, followed 
    by an ASCII error message that might contain additional, operating 
    system specific information.
    """
    def __init__(self, error_code: int, error_msg: str):
        super().__init__(f'TFTP Error {error_code}')
        self.error_code = error_code
        self.error_msg = error_msg
    #:
#:


################################################################################
##
##      FILE utils.py
##      COMMON UTILITIES
##      Mostly related to network tasks
##
################################################################################

def _make_is_valid_hostname():
    allowed = re.compile(r"(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    def _is_valid_hostname(hostname):
        """
        From: http://stackoverflow.com/questions/2532053/validate-a-hostname-string
        See also: https://en.wikipedia.org/wiki/Hostname (and the RFC 
        referenced there)
        """
        if not 0 < len(hostname) <= 255:
            return False
        if hostname[-1] == ".":
            # strip exactly one dot from the right, if present
            hostname = hostname[:-1]
        return all(allowed.match(x) for x in hostname.split("."))
    return _is_valid_hostname
#:
is_valid_hostname = _make_is_valid_hostname()


def get_host_info(server_addr: str) -> tuple[str, str]:
    """
    Returns the server ip and hostname for server_addr. This param may
    either be an IP address, in which case this function tries to query
    its hostname, or vice-versa.
    This functions raises a ValueError exception if the host name in
    server_addr is ill-formed, and raises NetworkError if we can't get
    an IP address for that host name.
    TODO: refactor code...
    """

    # Allow explicitly localhost and 127.0.0.1
    if server_addr in ("127.0.0.1", "localhost"):
        return "127.0.0.1", "localhost"

    try:
        ipaddress.ip_address(server_addr)
    except ValueError:
        # server_addr not a valid ip address, then it might be a 
        # valid hostname
        if not is_valid_hostname(server_addr):
            raise ValueError(f"Invalid hostname: {server_addr}.")
        server_name = server_addr
        try:
            # gethostbyname_ex returns the following tuple: 
            # (hostname, aliaslist, ipaddrlist)
            server_ip = socket.gethostbyname_ex(server_name)[2][0]
        except socket.gaierror:
            raise NetworkError(f"Unknown server: {server_name}.")
    else:  
        # server_addr is a valid ip address, get the hostname
        # if possible
        server_ip = server_addr
        try:
            # returns a tuple like gethostbyname_ex
            server_name = socket.gethostbyaddr(server_ip)[0]
        except socket.herror:
            server_name = ''
    return server_ip, server_name
#:


def is_ascii_printable(txt: str) -> bool:
    return set(txt).issubset(string.printable)
    # ALTERNATIVA: return not set(txt) - set(string.printable)
#:

def clearScreen() -> None:
    # os.system('cls' if os.name == 'nt' else 'clear')
    if os.name == 'posix':
        subprocess.run(['clear'])
    elif os.name == 'nt':
        subprocess.run(['cls'], shell = True)
#:

if __name__ == "__main__":
    pass
    ## Test the packing and unpacking functions
    #print(f"pack_rrq('ficheiro.txt'): {pack_rrq('ficheiro.txt')}")          # b'\x01\x00ficheiro.txt\x00octet\x00'
    #s = unpack_rrq(b'\x00\x01ficheiro.txt\x00octet\x00')
    #print(f"unpack_rrq(b''\\x00\\x01ficheiro.txt\\x00octet\\x00'): {s}")    # ficheiro.txt
    #print()
    #print(f"pack_wrq('ficheiro.txt'): {pack_wrq('ficheiro.txt')}")          # b'\x02\x00ficheiro.txt\x00octet\x00'
    #s = unpack_wrq(b'\x00\x02ficheiro.txt\x00octet\x00')
    #print(f"unpack_wrq(b''\\x00\\x02ficheiro.txt\\x00octet\\x00'): {s}")    # ficheiro.txt
    #print()
#
    #buffer = bytearray(512)
    #filename = "ficheiro.txt"
    #offset = 0
    #
    #print(f"Packing RRQ into buffer at offset {offset} for filename '{filename}'")
    #print('pack__rq_into(buffer, offset, TFTPOpcode.RRQ, filename)')
    #nbytes = pack__rq_into(buffer, offset, TFTPOpcode.RRQ, filename)
    #print(f"Bytes escritos: {nbytes}")
    #print(f"Buffer (hex): {buffer[:nbytes].hex()}")
    #print()
#
    #print(f"Unpacking from buffer at offset {offset}'")
    #print(f'unpack__rq_into(buffer, offset): {unpack__rq_from(buffer, offset)}')
#
    #err = pack_err(2, "Access violation")
    #print(f"pack_err(2, 'Access violation'): {err}")
    #err_num, err_msg = unpack_err(err)
    #print(f"unpack_err(err): {err_num}, {err_msg}")
#
#   #server_addr = ('127.0.0.1', 69)
    #client_get_file(server_addr, 'Projecto2.pdf')
    #client_put_file(server_addr, 'Proj2.pdf')
