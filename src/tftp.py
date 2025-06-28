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

# Usage:
# print(TFTPOpcode.RRQ)   # 1
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

# Usage:
# print(TFTPErrorCode.FILE_NOT_FOUND.value)   # 1
# print(TFTPErrorCode.FILE_NOT_FOUND.message) # "File not found"
#:


# ##############################################################################
#
# SEND AND RECEIVE FILES
#
# ##############################################################################
# O professor ?irá? ainda libertar vídeos de explicação e com walkthroughs


# ##############################################################################
#
# PACKET PACKING AND UNPACKING
#
# ##############################################################################
# Endianness, Big-endian, Little-endian https://en.wikipedia.org/wiki/Endianness
# Use '!H' for network protocols, such as TFTP, to ensure interoperability.
# 'H' should only be used if you are certain all participants use the same
# endianness (which is rare in networks).
# c = struct.Struct('!H', TFTPOpcode.RRQ)

# Talvez criar uma função genérica para empacotar e outra para desempacotar?
# pack_into e unpack_from são mais eficientes. Usar na função genérica.
# Criar uma classe de exceções personalizada para erros do TFTP?

def pack_rrq(filename, mode=DEFAULT_MODE) -> bytes:
    filename_bytes = filename.encode() + b'\x00'
    mode_bytes = mode.encode() + b'\x00'
    rrq_fmt = f'H{len(filename_bytes)}s{len(mode_bytes)}s'
    return struct.pack(rrq_fmt, TFTPOpcode.RRQ.value, filename_bytes, mode_bytes)
#:


def pack_wrq(filename, mode=DEFAULT_MODE) -> bytes:
    filename_bytes = filename.encode() + b'\x00'
    mode_bytes = mode.encode() + b'\x00'
    wrq_fmt = f'H{len(filename_bytes)}s{len(mode_bytes)}s'
    return struct.pack(wrq_fmt, TFTPOpcode.WRQ.value, filename_bytes, mode_bytes)
#:

# struct.unpack() expects a fixed-size format string, so we need to handle
#  variable-length strings manually.
def unpack_rrq(packet: bytes) -> str:
    # Minimum size for RRQ packet is 4 bytes (opcode + 2 null-terminated strings)
    if len(packet) < 4:
        raise ValueError("Invalid RRQ packet size")
    
    # Unpack the fixed-size part of the packet
    opcode = struct.unpack('H', packet[:2])[0]
    if opcode != TFTPOpcode.RRQ.value:
        raise ValueError("Invalid RRQ packet")

    # The rest of the packet contains the filename and mode, which are
    #  null-terminated strings
    rest = packet[2:]
    filename = rest.split(b'\x00', 1)[0].decode()
    return filename
#:


def unpack_wrq(packet: bytes) -> str:
    # Minimum size for WRQ packet is 4 bytes (opcode + 2 null-terminated strings)
    if len(packet) < 4:
        raise ValueError("Invalid WRQ packet size")
    
    # Unpack the fixed-size part of the packet
    opcode = struct.unpack('H', packet[:2])[0]
    if opcode != TFTPOpcode.WRQ.value:
        raise ValueError("Invalid WRQ packet")

    # The rest of the packet contains the filename and mode, which are
    #  null-terminated strings
    rest = packet[2:]
    filename = rest.split(b'\x00', 1)[0].decode()
    return filename
#:


if __name__ == "__main__":
    print(pack_rrq('ficheiro.txt'))     # b'\x01\x00ficheiro.txt\x00octet\x00'
    print(pack_wrq('ficheiro.txt'))     # b'\x02\x00ficheiro.txt\x00octet\x00'
    print(unpack_rrq(b'\x01\x00ficheiro.txt\x00octet\x00'))  # ficheiro.txt
    print(unpack_wrq(b'\x02\x00ficheiro.txt\x00octet\x00'))  # ficheiro.txt