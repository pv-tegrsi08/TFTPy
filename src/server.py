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
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR
# import socketserver   Parece mais difícil de lidar com portos efémeros
import threading
from tftp import (
    unpack_opcode, unpack_rrq, unpack_wrq, pack_dat, pack_ack, pack_err,
    unpack_ack, unpack_err, pack_rrq, pack_wrq, 
    TFTPOpcode, is_ascii_printable, TFTPError, MAX_DATA_LEN, INACTIVITY_TIMEOUT,
    DEFAULT_BUFFER_SIZE
)


def send_dir(transfer_sock, client_addr, server_dir):
    """
    Sends the local directory listing to the client, responding to a dir request
    """

    if os.name == 'nt':
        # Windows
        cmd = f'dir "{server_dir}"'
    else:
        # Linux/macOS
        cmd = f'ls -lh "{server_dir}"'
    listing = os.popen(cmd).read().encode('utf-8')

    total_len = len(listing)
    block_number = 1
    offset = 0

    print(f"[{time.strftime('%H:%M:%S')}] DIR request from {client_addr} for '{server_dir}'")

    while True:
        data = listing[offset:offset + MAX_DATA_LEN]
        dat_packet = pack_dat(block_number, data)

        while True:
            transfer_sock.sendto(dat_packet, client_addr)
            try:
                transfer_sock.settimeout(INACTIVITY_TIMEOUT)
                packet, _ = transfer_sock.recvfrom(DEFAULT_BUFFER_SIZE)
            except TimeoutError:
                print(f"Timeout waiting for ACK for block {block_number} from {client_addr}. Aborting transfer.")
                return
            except Exception as e:
                print(f"Error during DIR transfer: {e}")
                return

            opcode = unpack_opcode(packet)
            if opcode == TFTPOpcode.ACK:
                ack_block = unpack_ack(packet)
                if ack_block == block_number:
                    break
                else:
                    print(f"Invalid ACK block number: {ack_block} (expected {block_number})")
                    continue
            elif opcode == TFTPOpcode.ERROR:
                err_code, err_msg = unpack_err(packet)
                print(f"TFTP error from client: {err_code} {err_msg}")
                return
            else:
                print(f"Invalid packet opcode: {opcode}. Expecting ACK.")
                continue

        offset += MAX_DATA_LEN
        block_number += 1

        if len(data) < MAX_DATA_LEN:
            break

    print(f"[{time.strftime('%H:%M:%S')}] DIR listing sent to {client_addr} ({total_len} bytes)")
    return total_len
#:

#def get_file(server_addr: INET4Address, remote_file: str, local_file: str = None) -> int:
#    """
#    Get the remote file given by `remote_file` thougth a TFTP RRQ
#    connection to remote server at `server_addr`.
#    """
#    if local_file is None:
#        local_file = remote_file
#
#    with socket(AF_INET, SOCK_DGRAM) as sock:
#        sock.settimeout(INACTIVITY_TIMEOUT)
#        with open(local_file, 'wb') as out_file:
#            rqq = pack_rrq(remote_file)
#            next_block_number = 1
#            sock.sendto(rqq, server_addr)
#
#            while True:
#                packet, server_address = sock.recvfrom(DEFAULT_BUFFER_SIZE)
#                opcode = unpack_opcode(packet)
#
#                if opcode == TFTPOpcode.DATA:
#                    block_number, data = unpack_dat(packet)
#
#                    if block_number not in (next_block_number, next_block_number - 1):
#                        error_msg = f'Invalid block number: {block_number}'
#                        raise ProtocolError(error_msg)
#                    out_file.write(data)
#                    next_block_number += 1
#
#                    ack = pack_ack(block_number)
#                    sock.sendto(ack, server_address)
#
#                    if len(data) < MAX_DATA_LEN:
#                        return block_number * DEFAULT_BUFFER_SIZE + len(data)
#                    
#                elif opcode == TFTPOpcode.ERROR:
#                    err_code, err_msg = unpack_err(packet)
#                    raise Err(err_code, err_msg)
#
#                else:
#                    error_msg = f'Invalid packet opcode: {opcode}. Expecting {TFTPOpcode.DATA=}'
#                    raise ProtocolError(error_msg)
##:



#def put_file(server_addr: INET4Address, remote_file: str, local_file: str = None) -> int:
#    """
#    Put the local file given by `filename` through a TFTP WRQ
#    connection to remote server at `server_addr`.
#    """
#    if local_file is None:
#        local_file = remote_file
#
#    # The TFTP in /etc/default/tftpd-hpa defaults to TFTP_OPTIONS="--secure"
#    #  meaning that it only allows puts of existing files, returning error 1!!
#    # Change to TFTP_OPTIONS="--secure --create --umask 022"
#    with socket(AF_INET, SOCK_DGRAM) as sock:
#        sock.settimeout(INACTIVITY_TIMEOUT)
#        with open(local_file, 'rb') as in_file:
#            wrq = pack_wrq(remote_file)
#            sock.sendto(wrq, server_addr)
#
#            next_block_number = 1
#            while True:
#                packet, server_address = sock.recvfrom(DEFAULT_BUFFER_SIZE)
#                opcode = unpack_opcode(packet)
#
#                if opcode == TFTPOpcode.ACK:
#                    block_number = unpack_ack(packet)
#
#                    if block_number != next_block_number - 1:
#                        error_msg = f'Invalid block number: {block_number}'
#                        raise ProtocolError(error_msg)
#
#                    data = in_file.read(MAX_DATA_LEN)
#                    if not data:
#                        return block_number * DEFAULT_BUFFER_SIZE + len(data)
#
#                    dat_packet = pack_dat(next_block_number, data)
#                    sock.sendto(dat_packet, server_address)
#                    next_block_number += 1
#
#                elif opcode == TFTPOpcode.ERROR:
#                    err_code, err_msg = unpack_err(packet)
#                    raise Err(err_code, err_msg)
#
#                else:
#                    error_msg = f'Invalid packet opcode: {opcode}. Expecting {TFTPOpcode.ACK=}'
#                    raise ProtocolError(error_msg)
##:


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

            # DIR
            if filename == '':
                send_dir(transfer_sock, client_addr, server_dir)
                return

            #send_file(transfer_sock, client_addr, )

        elif opcode == TFTPOpcode.WRQ:
            filename, mode = unpack_wrq(data)
            if not is_ascii_printable(filename):
                err = pack_err(TFTPError.ACCESS_VIOLATION.value[0], "Invalid filename.")
                transfer_sock.sendto(err, client_addr)
                return

            #receive_file(transfer_sock, client_addr, )

        else:
            err = pack_err(TFTPError.ILLEGAL_OPERATION.value[0], "Illegal TFTP operation.")
            transfer_sock.sendto(err, client_addr)
            print(f"[{time.strftime('%H:%M:%S')}] Invalid opcode from {client_addr}")
            return


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

    # Validates args
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
        # Project, page 9
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, True)
        sock.bind(('', port))
    except Exception:
        print(f"Unable to bind to port '{port}'.")
        sys.exit(1)

    hostname = socket.gethostname()
    print(f"Waiting for requests on '{hostname}' port '{port}'")

    while True:
        data, client_addr = sock.recvfrom(DEFAULT_BUFFER_SIZE)
        threading.Thread(target=do_request, args=(data, client_addr, directory), daemon=True).start()
#:


if __name__ == "__main__":
    main()
#: