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

from distkeras.networking import allocate_tcp_listening_port
from distkeras.networking import allocate_udp_listening_port
from distkeras.networking import connect
from distkeras.networking import determine_host_address
from distkeras.networking import recv_data
from distkeras.networking import send_data

from distkeras.native.jobs import DataTransferJob
from distkeras.native.jobs import TrainingJob

from distkeras.utils import serialize_keras_model
from distkeras.utils import deserialize_keras_model

from distkeras.native.parameter_servers import ParameterServer

from multiprocessing import Process

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
    MULTICAST_GROUP = '225.0.0.250'

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
        self.thread_service_multicast = threading.Thread(target=self.service_multicast)
        self.thread_service_multicast.start()

    def initialize_allocation_service(self):
        fd, port = allocate_tcp_listening_port(port=self.port_allocation)
        self.socket = fd
        self.socket.settimeout(1.0)
        self.port_allocation = port

    def allocate_session(self, identifier):
        # Construct a dictionary.
        d = {
            DataTransferJob.IDENTIFIER: allocate_data_transfer_session,
            TrainingJob.IDENTIFIER_ALLOCATE_PS: allocate_parameter_server_session,
            TrainingJob.IDENTIFIER_ALLOCATE_WORKER: allocate_worker_session
        }
        # Choose the session allocation function.
        session = d[identifier]()

        return session

    def allocate_process(self, identifier, parameters):
        session = self.allocate_session(identifier)
        description = session.get_description()
        session.set_parameters(parameters)
        session.process_parameters()
        p = Process(target=session.run)
        p.start()

        return description

    def handle_allocation_connection(self, conn, addr):
        data = recv_data(conn)
        identifier = data['job_identifier']
        parameters = data['parameters']
        description = self.allocate_process(identifier, parameters)
        data = {}
        data['description'] = description
        send_data(conn, data)

    def start(self):
        self.initialize_multicast_service()
        self.initialize_allocation_service()
        super(Daemon, self).start()

    def run(self):
        while self.running:
            try:
                conn, addr = self.socket.accept()
                self.handle_allocation_connection(conn, addr)
                conn.close()
            except:
                pass

    def stop(self):
        self.running = False
        self.socket_multicast.close()
        self.socket.close()

    def join(self):
        self.thread_service_multicast.join()

## END Daemon. #################################################################

## BEGIN Daemon sessions. ######################################################

class Session(object):

    def __init__(self):
        self.parameters = None
        self.host_address = determine_host_address()

    def set_parameters(self, parameters):
        self.parameters = parameters

    def process_parameters(self):
        # Nothing to do here.
        pass

    def get_description(self):
        raise NotImplementedError

    def run(self):
        raise NotImplementedError


def allocate_data_transfer_session():
    session = DataTransferSession()

    return session

class DataTransferSession(Session):

    TRANSFER_CHUNKS = 65536

    def __init__(self):
        Session.__init__(self)
        # Allocate a listening TCP port.
        socket, port = allocate_tcp_listening_port()
        self.socket = socket
        self.port = port
        # Set data transfer settings.
        self.transferring = True
        self.transfer_socket = None

    def get_description(self):
        return (self.host_address, self.port)

    def create_directory(self, path):
        # Create the directory.
        os.makedirs(path)
        # Notify the client that the creating is succesfull.
        response = {}
        response['path'] = path
        response['status'] = True
        send_data(self.transfer_socket, response)

    def receive_file(self, path, file_size):
         # Notify the client that the file is going to be created.
        response = {}
        response['path'] = path
        response['status'] = False
        response['creating'] = True
        send_data(self.transfer_socket, response)
        bytes_read = 0
        with open(path, "wb") as f:
            while bytes_read < file_size:
                buffer = self.transfer_socket.recv(self.TRANSFER_CHUNKS)
                bytes_read += len(buffer)
                f.write(buffer)
        # Notify the client that the creating is succesfull.
        response = {}
        response['path'] = path
        response['status'] = True
        send_data(self.transfer_socket, response)

    def run(self):
        conn, addr = self.socket.accept()
        self.transfer_socket = conn
        while self.transferring:
            # Fetch the next header.
            header = recv_data(conn)
            # Fetch the required parameters.
            path = header['path']
            is_directory = header['is_dir']
            self.transferring = not header['stop_transfer']
            if not self.transferring:
                break
            # Check if the path exists on the local machine.
            if os.path.exists(path):
                response = {}
                response['path'] = path
                response['status'] = False
                send_data(self.transfer_socket, response)
                continue
            if is_directory:
                self.create_directory(path)
            else:
                file_size = header['file_size']
                self.receive_file(path, file_size)
        conn.close()
        self.close_socket()


def allocate_parameter_server_session():
    return ParameterServerSession()

class ParameterServerSession(Session):

    def __init__(self):
        Session.__init__(self)
        # Allocate a port for job-control.
        socket, port = allocate_tcp_listening_port()
        self.control_socket = socket
        self.control_port = port
        # Allocate a port for worker communications.
        socket, port = allocate_tcp_listening_port()
        self.worker_socket = socket
        self.worker_port = port
        # Parameter Server instance.
        self.ps = None

    def get_description(self):
        control_description = (self.host_address, self.control_port)
        ps_description = (self.host_address, self.worker_port)

        return [control_description, ps_description]

    def process_parameters(self):
        identifier = self.parameters['parameter_server_identifier']
        model = deserialize_keras_model(self.parameters['model'])
        try:
            self.ps = ParameterServer(identifier, self.worker_socket, self.worker_port, model, self.parameters)
            self.ps.start()
        except Exception as e:
            print(e)

    def handle_control_connection(self):
        try:
            conn, addr = self.control_socket.accept()
            self.ps.stop()
            conn.close()
        except Exception as e:
            print(e)

    def run(self):
        # Wait for a control connection.
        self.handle_control_connection()
        # Wait for the parameter server to stop gracefully.
        self.ps.join()
        # Close the control and worker ports.
        # Note the worker port is closed by the PS.
        self.control_socket.close()


def allocate_worker_session():
    return WorkerSession()

class WorkerSession(Session):

    def __init__(self):
        Session.__init__(self)
        # TODO Implement.
        print("Allocated worker session")

    def get_description(self):
        # TODO Implement.
        return None

    def process_parameters(self):
        # TODO Implement.
        print("Processing worker parameters")

    def run(self):
        # TODO Implement.
        print("Running worker session")


## END Daemon sessions. ########################################################
