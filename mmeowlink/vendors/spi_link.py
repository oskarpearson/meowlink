import atexit
import json
import subprocess
import sys

from .. exceptions import CommsException

class SPILink:
    backend = None
    program = '/usr/local/bin/spilink'

    def __init__(self):
        if SPILink.backend is None:
            SPILink.backend = subprocess.Popen(SPILink.program,
                                               stdin=subprocess.PIPE,
                                               stdout=subprocess.PIPE,
                                               stderr=sys.stderr)
            atexit.register(self.exit)
        self.request_channel = SPILink.backend.stdin
        self.response_channel = SPILink.backend.stdout
        self.timeout = 1

    def exit(self):
        SPILink.backend.stdin.close()
        SPILink.backend.wait()

    def write(self, string, repetitions=1, timeout=None):
        if timeout is None:
            timeout = self.timeout
        data = str(string).encode('base64')
        usecs = int(timeout * 1000000)
        json.dump({'Command': 'send_packet',
                   'Data': data,
                   'Repeat': repetitions,
                   'Timeout': usecs},
                  self.request_channel)
        self.ignore_response()

    def read(self, timeout=None):
        if timeout is None:
            timeout = self.timeout
        usecs = int(timeout * 1000000)
        json.dump({'Command': 'get_packet',
                   'Timeout': usecs},
                  self.request_channel)
        return self.handle_response()

    def write_and_read(self, string, repetitions=1, timeout=None):
        if timeout is None:
            timeout = self.timeout
        data = str(string).encode('base64')
        usecs = int(timeout * 1000000)
        json.dump({'Command': 'send_and_listen',
                   'Data': data,
                   'Repeat': repetitions,
                   'Timeout': usecs},
                  self.request_channel)
        return self.handle_response()

    def handle_response(self):
        # Don't use json.load() because that will block.
        # Instead, rely on the newline written by Go's JSON encoder.
        response = json.loads(self.response_channel.readline())
        if response['Error'] or len(response['Data']) == 0:
            raise CommsException("No response or receive error")
        return bytearray(response['Data'].decode('base64'))

    def ignore_response(self):
        response = json.loads(self.response_channel.readline())
