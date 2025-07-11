#!/usr/bin/env python3
"""
TFTPy is a simple implementation of the TFTP protocol that can be used to 
 transfer files between a client and a server.
It supports both the get and put commands to download and upload files respectively.

This server is invoked with the following command:
    $ python3 server.py [directory] [port]

Successfully tested on the following platforms:
    Windows 10 22H2 with Python 3.12.1
    Linux Mint 21.2 with Python 3.12.1

Libraries used (all from Python's standard library):
    os
    sys
    time
    socket
    threading

External libraries used requiring pip install:
    docopt

A virtual environment (.venv) was used to isolate the project.

(c) 2025 João Galamba, Pedro Dores, Pedro Vieira

Source code licensed under GPLv3. Please refer to:
    https://www.gnu.org/licenses/gpl-3.0.en.html
"""

import os
import sys
import time
from docopt import docopt
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR, gethostname
# import socketserver   Parece mais difícil de lidar com portos efémeros
import threading
from tftp import (
    unpack_opcode, unpack_rrq, unpack_wrq, pack_err, TFTPOpcode, is_ascii_printable,
    TFTPError, server_send_dir, server_send_file, server_receive_file,
    INACTIVITY_TIMEOUT, DEFAULT_BUFFER_SIZE
)

def do_request(data, client_addr, server_dir):
    with socket(AF_INET, SOCK_DGRAM) as transfer_sock:
        transfer_sock.settimeout(INACTIVITY_TIMEOUT)
        transfer_sock.bind(('', 0))  # Porto efémero

        opcode = unpack_opcode(data)
        if opcode == TFTPOpcode.RRQ:
            filename, mode = unpack_rrq(data)
            if not is_ascii_printable(filename) or '/' in filename or '\\' in filename:
            # If the filename is not printable or contains directory traversal characters, return an error.
                err = pack_err(TFTPError.ACCESS_VIOLATION.value[0], "Invalid filename.")
                transfer_sock.sendto(err, client_addr)
                return

            # RRQ DIR
            if filename == '':
                server_send_dir(transfer_sock, client_addr, server_dir)
                return

            # RRQ FILE
            # Checks safe path. If client tries to access files outside the server directory
            #  using something like ../private/file.txt, will generate an Access violation.
            local_file = os.path.abspath(os.path.join(server_dir, filename))
            server_dir_abs = os.path.abspath(server_dir)
            if os.path.commonpath([local_file, server_dir_abs]) != server_dir_abs:
                err = pack_err(TFTPError.ACCESS_VIOLATION.value[0], "Access violation.")
                transfer_sock.sendto(err, client_addr)
                return

            if not os.path.isfile(local_file):
                err = pack_err(TFTPError.FILE_NOT_FOUND.value[0], "File not found.")
                transfer_sock.sendto(err, client_addr)
                return

            server_send_file(transfer_sock, client_addr, local_file, filename)

        elif opcode == TFTPOpcode.WRQ:
            filename, mode = unpack_wrq(data)
            if not is_ascii_printable(filename) or '/' in filename or '\\' in filename:
            # If the filename is not printable or contains directory traversal characters, return an error.
                err = pack_err(TFTPError.ACCESS_VIOLATION.value[0], "Invalid filename.")
                transfer_sock.sendto(err, client_addr)
                return

            # Checks safe path. If client tries to write files outside the server directory
            #  using something like ../private/file.txt, will generate an Access violation.
            local_file = os.path.abspath(os.path.join(server_dir, filename))
            server_dir_abs = os.path.abspath(server_dir)
            if os.path.commonpath([local_file, server_dir_abs]) != server_dir_abs:
                err = pack_err(TFTPError.ACCESS_VIOLATION.value[0], "Access violation.")
                transfer_sock.sendto(err, client_addr)
                return

            # If the local_file already exists, return an error. See project statement, page 12
            if os.path.exists(local_file):
                err = pack_err(TFTPError.FILE_EXISTS.value[0], "File already exists.")
                transfer_sock.sendto(err, client_addr)
                return

            server_receive_file(transfer_sock, client_addr, local_file, filename)

        else:
            err = pack_err(TFTPError.ILLEGAL_OPERATION.value[0], "Illegal TFTP operation.")
            transfer_sock.sendto(err, client_addr)
            print(f"[{time.strftime('%H:%M:%S')}] Invalid opcode from {client_addr}")
            return
#:

def main():
    doc = """TFTP Server.
TFTPy: A TFTP server written in Python.

Usage:
  server.py [<directory>] [<port>]

Options:
    -h, --help        Show this help message
    <directory>       Directory to serve [default: .]
    <port>            UDP port to use [default: 69]
"""
    args = docopt(doc)

    # Validates docopt args
    directory = args['<directory>'] or os.getcwd()
    if not os.path.isdir(directory):
        print(f"Directory '{directory}' does not exist.")
        sys.exit(1)

    port = 0
    port_str = (args['<port>'] or '69')
    if port_str.isdigit():
        port = int(port_str)
    if not (0 < port < 65536):
        print(f"Invalid port number: {port_str}")
        sys.exit(1)

    try:
        # Project statement, page 9
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, True)
        sock.bind(('', port))
        sock.settimeout(1)  # Allowing Windows to treat a Ctrl+C as a KeyboardInterrupt
    except Exception:
        print(f"Unable to bind to port '{port}'.")
        sys.exit(1)

    hostname = gethostname()
    print(f"Waiting for requests on '{hostname}' port '{port}'")

    try:
        while True:
            try:
                data, client_addr = sock.recvfrom(DEFAULT_BUFFER_SIZE)
                threading.Thread(target=do_request, args=(data, client_addr, directory), daemon=True).start()
            except TimeoutError:
                continue  # Allowing Windows to treat a Ctrl+C as a KeyboardInterrupt
            except Exception as e:
                print(f"Socket error: {e}")
    except KeyboardInterrupt:
        print("\nExiting TFTP server..")
        print("Goodbye!\n")
        sock.close()
        sys.exit(0)
#:


if __name__ == "__main__":
    main()
#: