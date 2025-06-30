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
import subprocess
import textwrap

import readline
# fix tab-completion behaviour on OS X (which uses libedit)
if sys.platform == 'darwin':  
    if 'libedit' in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")

# Em caso de erro "ModuleNotFoundError: No module named 'docopt'"", correr:
# source .venv/bin/activate
# pip install docopt
from docopt import docopt

from tftp import get_file


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

    if args['get']:
        print("GET")
    elif args['put']:
        print("PUT")
    else:
        exec_tftp_shell(args['<server>'], int(args['--port']))
#:

def exec_tftp_shell(server: str, server_port: int):
    exit_code = 0
    print(f"Exchaging files with server '{server}' (<ip do servidor>)")
    print(f"Server port is {server_port}\n")

    try:
        while True:
            cmd = input("tftp client> ")

            match cmd.split():
                case ['get', remote_file, *local_file]:
                    local_file = local_file[0] if local_file else remote_file
                    print(f"GET args => {remote_file=} {local_file=}")
                case ['put', local_file, *remote_file]:
                    remote_file = remote_file[0] if remote_file else local_file
                    print(f"PUT args => {local_file=} {remote_file=}")

                case ['help']:
                    print(textwrap.dedent(
                        """
                        Commands:
                            get remote_file [local_file] - get a file from server and save it
                                                           as local_file
                            put local_file [remote_file] - send a file to server and store it 
                                                           as remote_file
                            dir                          - obtain a listing of remote files
                            cls | clear                  - clear screen
                            quit                         - exit TFTP client
                        """
                    ))

                case ['quit']:
                    break
                case ['cls' | 'clear']:
                    clear_screen()
                case _:
                    print(f"Unknown command: '{cmd}'")
    except KeyboardInterrupt:
        print("\nCTRL+C pressed")
    except EOFError:
        print("\nNo more input")
    finally:
        print("Exiting TFTP client.")
        print("Goodbye!")
        sys.exit(exit_code)
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