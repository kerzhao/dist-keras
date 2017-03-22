"""Daemon module.

Describes all functionality of a ML job daemon scheduler.
Basically, a Daemon in a dist-keras context is responsible for the
allocation of certain resources. Think of it as an easy way to allocate
specific algorithms on different machines, without having the burden to
SSH and copy files to those machines. Furthermore, the deamons are responsible
to bring the trainers in direct contact with the parameter servers and workers
for additional training metrics.
"""

## BEGIN Imports. ##############################################################

from distkeras.networking import determine_host_address
from distkeras.networking import allocate_udp_listening_port
from distkeras.networking import allocate_tcp_listening_port
from distkeras.networking import connect
from distkeras.networking import recv_data
from distkeras.networking import send_data

import cPickle as pickle

import os

import socket

import struct

import threading

## END Imports. ################################################################

## BEGIN Daemon. ###############################################################

class Daemon(threading.Thread):
    """A dist-keras native daemon process which will run on many different machines,
    and spawns training resources accordingly."""

    PORT_MULTICAST = 6000
    DGRAM_BUFFER_SIZE = 10000
    MULTICAST_GROUP = '224.1.1.1'

    def __init__(self):
        # Allocate superclass members.
        threading.Thread.__init__(self)
        # Assign default values to daemon properties.
        self.multicast_group = self.MULTICAST_GROUP
        self.port_multicast = self.PORT_MULTICAST
        self.port_allocation = 0
        self.running = True
        self.socket = None
        self.socket_multicast = None
        self.thread_service_allocation = None
        self.thread_service_multicast = None
        self.threads_multicast = []
        self.threads_allocation = []

    def set_port_multicast(self, port):
        self.port_multicast = port

    def set_port_allocation(self, port):
        self.port_allocation = port

    def set_multicast_group(self, group):
        self.multicast_group = group

    def handle_multicast_message(self, address, port):
        try:
            # Open a connection with the remote host.
            fd = connect(address, port)
            # Prepare the datastructure which needs to be sent.
            data = {}
            data['address'] = determine_host_address()
            data['port'] = self.port_allocation
            print("Sending data to " + address)
            send_data(fd, data)
            # Close the connection.
            fd.close()
        except Exception as e:
            print(e)

    def service_multicast(self):
        # Define the max message size.
        max_message_size = 0xfffa # 0xffff - 5
        while self.running:
            try:
                # Read messages from the Multicast buffer.
                buffer = self.socket_multicast.recv(self.DGRAM_BUFFER_SIZE)
                message_size = int(buffer[:5])
                if message_size > max_message_size:
                    message_size = max_message_size
                message = buffer[5:5 + message_size]
                data = pickle.loads(message)
                # Fetch the IP address and port from the multicast message.
                address = data['address']
                port = data['port']
                # Allocate a thread to handle the multicast message.
                self.handle_multicast_message(address, port)
            except Exception as e:
                print(e)

    def initialize_multicast_service(self):
        # Join the multicast group.
        addrinfo = socket.getaddrinfo(self.multicast_group, None)[0]
        fd = socket.socket(addrinfo[0], socket.SOCK_DGRAM)
        fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        fd.bind((self.multicast_group, self.port_multicast))
        group_bin = socket.inet_pton(addrinfo[0], addrinfo[4][0])
        if addrinfo[0] == socket.AF_INET: # Check for IPv4
            mreq = group_bin + struct.pack('=I', socket.INADDR_ANY)
            fd.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        else:
            mreq = group_bin + struct.pack('@I', 0)
            fd.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)
        # Set the socket, and allocate the multicast service thread.
        self.socket_multicast = fd
        #self.socket_multicast.settimeout(1.0)
        self.thread_service_multicast = threading.Thread(target=self.service_multicast)
        self.thread_service_multicast.start()

    def initialize_allocation_service(self):
        fd, port = allocate_tcp_listening_port(port=self.port_allocation)
        self.socket = fd
        self.socket.settimeout(1.0)
        self.port_allocation = port

    def handle_allocation_connection(self, conn, addr):
        # Receive the datastructure from the connection.
        data = recv_data(conn)
        print(data)
        # TODO Implement.

    def start(self):
        self.initialize_multicast_service()
        self.initialize_allocation_service()

    def run(self):
        while self.running:
            try:
                conn, addr = self.socket.accept()
                self.handle_allocation_connection(conn, addr)
            except:
                pass

    def stop(self):
        self.running = False
        self.socket_multicast.close()
        self.socket.close()

    def join(self):
        self.thread_service_multicast.join()

## END Daemon. #################################################################
