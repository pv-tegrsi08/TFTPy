"""
TFTPy is a simple implementation of the TFTP protocol that can be used to
 transfer files between a client and a server.
This module is a common repository for the TFTP client and server
 implementations.
It handles all TFTP protocol details, such as packet formatting, error handling,
 and file transfer logic.
It is not intended to be run directly, but rather imported by the client and
 server modules.

# Successfully tested on the following platforms:
#    - Windows 10 22H2 with Python 3.12.1
#    - Linux Mint 21.2 with Python 3.12.1

# Libraries used (all from Python's standard library, no external libraries
#  installed via pip were used):
#    - sys
#    - time
#    - argparse
#    - os
#    - subprocess

A virtual environment (.venv) was used to isolate the project.

(c) 2025 João Galamba, Pedro Dores, Pedro Vieira

Source code licensed under GPLv3. Please refer to:
    https://www.gnu.org/licenses/gpl-3.0.en.html
"""

from enum import Enum
import struct
from utils import is_ascii_printable, TFTPValueError

# ##############################################################################
#
# PROTOCOL CONSTANTS AND TYPES
#
# ##############################################################################

MAX_DATA_LEN = 512      # in bytes
DEFAULT_MODE = "octet"  # transfer mode (one of 'octet', 'netascii', 'mail')

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

# class TFTPValueError(ValueError):
#     pass
#:

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


# ##############################################################################
#
# SEND AND RECEIVE FILES
#
# ##############################################################################
# O professor irá? ainda libertar vídeos de explicação e com walkthroughs


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

    fmt = f'!H{len(data)}s'
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
    return error_num, error_msg[:-1]
#:


# ##############################################################################
# PACKET PACKING AND UNPACKING (ALTERNATIVE)
# REVER
# Generic functions to pack / unpack both RRQ and WRQ packets using the more
#  efficient struct.pack_into() and struct.unpack_from() methods.
def pack__rq_into(buffer: bytearray, offset: int, opcode: TFTPOpcode, filename: str, mode=DEFAULT_MODE) -> int:
    # Packs a RRQ or a WRQ into the buffer at a specified offset.
    filename_bytes = filename.encode() + b'\x00'
    mode_bytes = mode.encode() + b'\x00'
    fmt = f'!H{len(filename_bytes)}s{len(mode_bytes)}s'
    struct.pack_into(fmt, buffer, offset, opcode.value, filename_bytes, mode_bytes)
    return struct.calcsize(fmt)  # Return the number of bytes packed into buffer
#:


def unpack__rq_from(buffer: bytes, offset=0) -> tuple[str, str]:
    # Unpacks a RRQ or a WRQ into the buffer at a specified offset.
    if len(buffer) < offset + 4:
        raise ValueError("Buffer too small for RRQ/WRQ packet.")
    
    opcode = struct.unpack_from('!H', buffer, offset)[0]
    if opcode not in (TFTPOpcode.RRQ.value, TFTPOpcode.WRQ.value):
        raise ValueError("Invalid ?RQ packet")

    offset += 2
    end_filename = buffer.index(0, offset)
    filename = buffer[offset:end_filename].decode()

    # O seguinte código não é necessário se implementarmos apenas o 
    #  transfer mode 'octet'. Falar com o Professor João Galamba.
    # offset = end_filename + 1
    # end_mode = buffer.index(0, offset)
    # mode = buffer[offset:end_mode].decode()
    # return filename, mode
    return filename
#:


if __name__ == "__main__":
    # Test the packing and unpacking functions
    print(f"pack_rrq('ficheiro.txt'): {pack_rrq('ficheiro.txt')}")          # b'\x01\x00ficheiro.txt\x00octet\x00'
    s = unpack_rrq(b'\x00\x01ficheiro.txt\x00octet\x00')
    print(f"unpack_rrq(b''\\x00\\x01ficheiro.txt\\x00octet\\x00'): {s}")    # ficheiro.txt
    print()
    print(f"pack_wrq('ficheiro.txt'): {pack_wrq('ficheiro.txt')}")          # b'\x02\x00ficheiro.txt\x00octet\x00'
    s = unpack_wrq(b'\x00\x02ficheiro.txt\x00octet\x00')
    print(f"unpack_wrq(b''\\x00\\x02ficheiro.txt\\x00octet\\x00'): {s}")    # ficheiro.txt
    print()

    buffer = bytearray(512)
    filename = "ficheiro.txt"
    offset = 0
    
    print(f"Packing RRQ into buffer at offset {offset} for filename '{filename}'")
    print('pack__rq_into(buffer, offset, TFTPOpcode.RRQ, filename)')
    nbytes = pack__rq_into(buffer, offset, TFTPOpcode.RRQ, filename)
    print(f"Bytes escritos: {nbytes}")
    print(f"Buffer (hex): {buffer[:nbytes].hex()}")
    print()

    print(f"Unpacking from buffer at offset {offset}'")
    print(f'unpack__rq_into(buffer, offset): {unpack__rq_from(buffer, offset)}')

    err = pack_err(2, "Access violation")
    print(f"pack_err(2, 'Access violation'): {err}")
    err_num, err_msg = unpack_err(err)
    print(f"unpack_err(err): {err_num}, {err_msg}")