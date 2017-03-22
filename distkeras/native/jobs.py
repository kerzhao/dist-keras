"""Jobs module.

Specifies client-side handling of remote jobs. Also defines what kind
of remote actions are possible
"""

## BEGIN Imports. ##############################################################

from distkeras.networking import recv_data
from distkeras.networking import send_data
from distkeras.networking import allocate_tcp_listening_port
from distkeras.networking import determine_host_address

import socket

import os

import struct

import cPickle as pickle

import threading

## END Imports. ################################################################

class Job(object):
    """An abstraction of a job. This class implements basic behaviour such
    as the collection of daemon nodes, and setting up communication with
    the remote server processes which have been allocated by the control
    daemons. Furthermore, it will set up all the resources, and specific
    dependencies depending on the parameterization of the job.
    """

    MULTICAST_GROUP = '224.1.1.1'
    MULTICAST_PORT = 6000
    MULTICAST_TTL = 3

    def __init__(self):
        # Set default multicast properties.
        self.multicast_group = self.MULTICAST_GROUP
        self.multicast_port = self.MULTICAST_PORT
        self.multicast_ttl = self.MULTICAST_TTL
        # Initialize list of job processes.
        self.job_processes = []
        self.num_job_processes = 0

    def set_multicast_group(self, group):
        self.multicast_group = group

    def get_multicast_group(self):
        return self.multicast_group

    def set_multicast_port(self, port):
        self.multicast_port = port

    def get_multicast_port(self):
        return self.multicast

    def set_multicast_ttl(self, ttl):
        self.multicast_ttl = ttl

    def get_multicast_ttl(self):
        return self.multicast_ttl

    def broadcast_job_announcement(self, address, port):
        addrinfo = socket.getaddrinfo(self.multicast_group, None)[0]
        fd = socket.socket(addrinfo[0], socket.SOCK_DGRAM)
        ttl_bin = struct.pack('@i', self.multicast_ttl)
        if addrinfo[0] == socket.AF_INET: # Check for IPv4
            fd.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl_bin)
        else: # Handle IPv4
            fd.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, ttl_bin)
        # Prepare the data to send.
        data = {}
        data['address'] = address
        data['port'] = port
        buffer = pickle.dumps(data, -1)
        buffer_size = str(len(buffer)).zfill(5)
        buffer = str(buffer_size) + buffer
        fd.sendto(buffer, (addrinfo[4][0], self.multicast_port))
        fd.close()

    def collect_daemons(self):
        """Returns all daemons listening to the specified broadcast address."""
        daemons = []

        # Allocate a port which handles the negotiation with the controller daemon.
        fd, port = allocate_tcp_listening_port()
        # Obtain the host address,
        host_address = determine_host_address()
        # Broadcast the job announcement.
        self.broadcast_job_announcement(host_address, port)
        # Wait for the daemons to connect, and supply their connection information.
        fd.settimeout(0.5)
        attempts = 0
        while attempts <= 5:
            try:
                # Accept a connection from the socket.
                conn, addr = fd.accept()
                data = recv_data(conn)
                description = (data['address'], data['port'])
                daemons.append(description)
                conn.close()
            except Exception as e:
                # Increase the number of attempts.
                attempts += 1
        # We have all the information, close the socket.
        fd.close()

        return daemons

    def run(self):
        """Runs the specified job. This method needs to be implemented
        in subclasses.
        """
        raise NotImplementedError
