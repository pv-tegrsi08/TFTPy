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


# TFTP error codes
class TFTPErrorCode(Enum):
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
#  RFC 1350 (TFTP):“Fields containing numbers are always in big-endian order
#  Usar '!H' or '>H' em vez de 'H'? Sim, ver página 8 do enunciado.
#
# Criar uma classe de exceções personalizada para erros do TFTP?

def pack_rrq(filename, mode=DEFAULT_MODE) -> bytes:
    filename_bytes = filename.encode() + b'\x00'
    mode_bytes = mode.encode() + b'\x00'
    rrq_fmt = f'!H{len(filename_bytes)}s{len(mode_bytes)}s'
    return struct.pack(rrq_fmt, TFTPOpcode.RRQ.value, filename_bytes, mode_bytes)
#:


def pack_wrq(filename, mode=DEFAULT_MODE) -> bytes:
    filename_bytes = filename.encode() + b'\x00'
    mode_bytes = mode.encode() + b'\x00'
    wrq_fmt = f'!H{len(filename_bytes)}s{len(mode_bytes)}s'
    return struct.pack(wrq_fmt, TFTPOpcode.WRQ.value, filename_bytes, mode_bytes)
#:


# struct.unpack() expects a fixed-size format string, so we need to handle
#  variable-length strings manually.
def unpack_rrq(packet: bytes) -> str:
    # Minimum size for RRQ packet is 4 bytes (opcode + 2 null-terminated strings)
    if len(packet) < 4:
        raise ValueError("Invalid WRQ packet size.")
    
    # Unpack the fixed-size part of the packet
    opcode = struct.unpack('!H', packet[:2])[0]
    if opcode != TFTPOpcode.RRQ.value:
        raise ValueError("Invalid RRQ packet.")

    # The rest of the packet contains the filename and mode, which are
    #  null-terminated strings. mode is always 'octet' in this implementation.
    rest = packet[2:]
    filename = rest.split(b'\x00', 1)[0].decode()
    return filename
#:


def unpack_wrq(packet: bytes) -> str:
    # Minimum size for WRQ packet is 4 bytes (opcode + 2 null-terminated strings)
    if len(packet) < 4:
        raise ValueError("Invalid WRQ packet size.")
    
    # Unpack the fixed-size part of the packet
    opcode = struct.unpack('!H', packet[:2])[0]
    if opcode != TFTPOpcode.WRQ.value:
        raise ValueError("Invalid WRQ packet.")

    # The rest of the packet contains the filename and mode, which are
    #  null-terminated strings. mode is always 'octet' in this implementation.
    rest = packet[2:]
    filename = rest.split(b'\x00', 1)[0].decode()
    return filename
#:


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


def unpack__rq_from(buffer: bytes, offset=0) -> str:
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
    s = unpack_rrq(b'\x00\x01\x00ficheiro.txt\x00octet')
    print(f"unpack_rrq(b''\\x00\\x01\\x00ficheiro.txt\\x00octet'): {s}")    # ficheiro.txt
    print()
    print(f"pack_wrq('ficheiro.txt'): {pack_wrq('ficheiro.txt')}")          # b'\x02\x00ficheiro.txt\x00octet\x00'
    s = unpack_wrq(b'\x00\x02\x00ficheiro.txt\x00octet\x00')
    print(f"unpack_wrq(b''\\x00\\x02\\x00ficheiro.txt\\x00octet\\x00'): {s}")    # ficheiro.txt
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