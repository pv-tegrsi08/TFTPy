#!/usr/bin/env python3
"""
# TFTPy a simple implementation of the TFTP protocol that can be used to transfer files between a client and a server.
# It supports both the get and put commands to download and upload files respectively.

# This server accepts these commands to interact with a client.
#    $ python3 server.py [-p serv_port] server
#    $ python3 client.py get [-p serv_port] server remote_file [local_file]
#    $ python3 client.py put [-p serv_port] server local_file [remote_file]


# Successfully tested on the following platforms:
#    - Windows 10 22H2 with Python 3.12.1
#    - Linux Mint 21.2 with Python 3.12.1

# Libraries used (all from Python's standard library, no external libraries installed via pip were used):
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

import os
import sys
import time
from docopt import docopt
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR, gethostname
# import socketserver   Parece mais difícil de lidar com portos efémeros
import threading

#from tftp import (
#    unpack_opcode, unpack_rrq, unpack_wrq, pack_dat, pack_ack, pack_err,
#    unpack_ack, unpack_err, pack_rrq, pack_wrq, 
#    TFTPOpcode, is_ascii_printable, TFTPError, MAX_DATA_LEN, INACTIVITY_TIMEOUT,
#    DEFAULT_BUFFER_SIZE
#)

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
            if not is_ascii_printable(filename):
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
            if not local_file.startswith(os.path.abspath(server_dir)):
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
            if not is_ascii_printable(filename):
                err = pack_err(TFTPError.ACCESS_VIOLATION.value[0], "Invalid filename.")
                transfer_sock.sendto(err, client_addr)
                return

            # Checks safe path. If client tries to write files outside the server directory
            #  using something like ../private/file.txt, will generate an Access violation.
            local_file = os.path.abspath(os.path.join(server_dir, filename))
            if not local_file.startswith(os.path.abspath(server_dir)):
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
    except Exception:
        print(f"Unable to bind to port '{port}'.")
        sys.exit(1)

    hostname = gethostname()
    print(f"Waiting for requests on '{hostname}' port '{port}'")

    try:
        while True:
            data, client_addr = sock.recvfrom(DEFAULT_BUFFER_SIZE)
            threading.Thread(target=do_request, args=(data, client_addr, directory), daemon=True).start()
    except KeyboardInterrupt:
        print("\nExiting TFTP server..")
        print("Goodbye!\n")
        sock.close()
        sys.exit(0)
#:


if __name__ == "__main__":
    main()
#: