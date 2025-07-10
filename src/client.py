#!/usr/bin/env python3
"""
TFTPy a simple implementation of the TFTP protocol that can be used to transfer files between a client and a server.
It supports both the get and put commands to download and upload files respectively.

This client accepts these commands to interact with a server.
    $ python3 client.py [-p serv_port] server
    $ python3 client.py get [-p serv_port] server remote_file [local_file]
    $ python3 client.py put [-p serv_port] server local_file [remote_file]


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
import cmd
import subprocess
from docopt import docopt
from tftp import client_get_file, client_put_file, INET4Address, Err
from tftp import is_ascii_printable, get_host_info

class TFTPCmdShell(cmd.Cmd):
    prompt = "tftp client> "

    def __init__(self, server_addr: INET4Address):
        super().__init__()
        self.server_addr = server_addr
        self.intro = f"Exchanging files with server '{server_addr[0]}'\nServer port is {server_addr[1]}\nType help or ? to list commands."

    def cmdloop(self, intro=None):
        while True:
            try:
                super().cmdloop(intro=intro)
                break
            except KeyboardInterrupt:
                print("^C pressed")
                print("Please write quit to exit.\n")

    def do_get(self, arg):
        "get remote_file [local_file]: Download a file from the server"
        args = arg.split()
        if not args:
            print("Usage: get remote_file [local_file]")
            return
        remote_file = args[0]
        local_file = args[1] if len(args) > 1 else remote_file
        if not is_ascii_printable(remote_file):
            print(f"Invalid file name: {remote_file}")
            return
        if local_file != remote_file and not is_ascii_printable(local_file):
            print(f"Invalid file name: {local_file}")
            return

        try:
            bytes_received = client_get_file(self.server_addr, remote_file, local_file)
            print(f"Received file '{local_file}' {bytes_received} bytes.")
        except Err as e:
            if e.error_code == 1:
                print("File not found.")
            else:
                print(f"TFTP error: {e.error_msg}")
        except Exception as e:
                print(f"Error downloading file: {e}")
        return

    def do_put(self, arg):
        "put local_file [remote_file]: Upload a file to the server"
        args = arg.split()
        if not args:
            print("Usage: put local_file [remote_file]")
            return
        local_file = args[0]
        remote_file = args[1] if len(args) > 1 else local_file
        if not is_ascii_printable(local_file):
            print(f"Invalid file name: {local_file}")
            return
        if local_file != remote_file and not is_ascii_printable(remote_file):
            print(f"Invalid file name: {remote_file}")
            return
        if not os.path.exists(local_file):
            print(f"File not found: {local_file}")
            return

        try:
            bytes_sent = client_put_file(self.server_addr, remote_file, local_file)
            print(f"Sent file '{local_file}' {bytes_sent} bytes.")
        except Err as e:
            if e.error_code == 1:
                print("File not found.")
            else:
                print(f"TFTP error: {e.error_msg}")
        except Exception as e:
            print(f"Error uploading file: {e}")
        return

    def do_dir(self, arg):
        "dir: List files on the server"
        temp_file = "_tftp_dir_listing.txt"
        try:
            bytes_received = client_get_file(self.server_addr, '', temp_file)
            with open(temp_file, "r") as f:
                print(f.read())
            os.remove(temp_file)
        except Exception:
            print("'dir' is not supported by this TFTP server.")
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def do_cls(self, arg):
        "cls: Clear the screen"
        clear_screen()
        return

    def do_clear(self, arg):
        "clear: Clear the screen"
        self.do_cls(arg)

    def do_quit(self, arg):
        "quit: Exit the TFTP client"
        print("Exiting TFTP client.")
        print("Goodbye!")
        return True

    def emptyline(self):
        pass  # Do nothing on empty input

    def default(self, line):
        print(f"Unknown command: {line}")
#:


def main():
    doc = """\
TFTPy: A TFTP client written in Python.

Usage:
    client.py [-p SERV_PORT] <server>
    client.py get [-p SERV_PORT] <server> <remote_file> [<local_file>]
    client.py put [-p SERV_PORT] <server> <local_file> [<remote_file>]

Options:
    -h, --help                      Show this help message
    -p SERV_PORT, --port=SERV_PORT  Port number [default: 69]
"""
    args = docopt(doc)
    # print(args)

    # Validates server
    try:
        server_ip, _ = get_host_info(args['<server>'])
    except Exception:
        print(f"Unknown server: {args['<server>']}")
        sys.exit(1) 

    # Validates port
    port_str = args['--port'] or "69"
    port = 0
    if port_str.isdigit():
        port = int(port_str)
    if not (0 < port < 65536):
        print(f"Invalid port number: {port_str}")
        sys.exit(1)


    if args['get'] or args['put']:
        # Validates filenames
        for arg in ['<local_file>', '<remote_file>']:
            filename = args[arg]
            if filename and not is_ascii_printable(filename):
                print(f"Invalid file name: {filename}")
                sys.exit(1)
        if args['put']:
            filename = args['<local_file>']
            if not os.path.exists(filename):
                print(f"File not found: {filename}")
                sys.exit(1)

        local_file = args['<local_file>']
        remote_file = args['<remote_file>']

    server_addr: INET4Address = (server_ip, port)

    if args['get']:
        local_file = local_file if local_file else remote_file
        try:
            bytes_received = client_get_file(server_addr, remote_file, local_file)
            print(f"Received file '{local_file}' {bytes_received} bytes.")
        except Err as e:
            if e.error_code == 1:
                print("File not found.")
            else:
                print(f"TFTP error: {e.error_msg}")
            sys.exit(1)
        except Exception as e:
            print(f"Error downloading file: {e}")
            sys.exit(1)

    elif args['put']:
        remote_file = remote_file if remote_file else local_file
        try:
            bytes_sent = client_put_file(server_addr, remote_file, local_file)
            print(f"Sent file '{local_file}' {bytes_sent} bytes.")
        except Err as e:
            if e.error_code == 1:
                print("File not found.")
            else:
                print(f"TFTP error: {e.error_msg}")
            sys.exit(1)
        except Exception as e:
            print(f"Error uploading file: {e}")
            sys.exit(1)

    else:
        shell = TFTPCmdShell(server_addr)
        shell.cmdloop()
#:


def clear_screen():
    """
    https://stackoverflow.com/questions/4553129/when-to-use-os-name-sys-platform-or-platform-system
    """
    match os.name:
        case 'nt':      # Windows (excepto Win9X)
            subprocess.run(['cls'], shell=True)
        case 'posix':   # Unixes e compatíveis como, por exemplo, macOS e WSL
            subprocess.run(['clear'])
#:


if __name__ == '__main__':
    main()