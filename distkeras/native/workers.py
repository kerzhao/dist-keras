"""Native workers module.

Specific distributed optimizer implementations.
"""

## BEGIN Imports. ##############################################################

from distkeras.networking import allocate_tcp_listening_port
from distkeras.networking import connect
from distkeras.networking import recv_data
from distkeras.networking import send_data

import numpy as np

import socket

import threading

## END Imports. ################################################################

class Worker(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.parameter_servers = []
        self.ps_sockets = []
        self.model = None
        self.parameters = None
        self.running = False

    def set_model(self, model):
        self.model = model

    def set_parameters(self, parameters):
        self.parameters = parameters

    def set_parameter_servers(self, parameter_servers):
        # TODO Implement.
        print(parameter_servers)

    def start(self):
        self.running = True
        super(Worker, self).start()

    def stop(self):
        self.running = False

    def disconnect_parameter_servers(self):
        for s in self.ps_sockets:
            s.close()

    def run(self):
        import time

        print("Worker working")
        time.sleep(10)
        # Close connection with the remote parameter servers.
        self.disconnect_parameter_servers()
        print("Worker done")
