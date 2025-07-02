import ipaddress
import string
import socket
import re
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

