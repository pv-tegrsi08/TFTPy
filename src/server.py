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

def main():
    print("This will be a TFTP server implementation.")
    print("     see you soon...")
#:

if __name__ == "__main__":
    main()