"""Jobs module.

Specifies client-side handling of remote jobs. Also defines what kind
of remote actions are possible
"""

## BEGIN Imports. ##############################################################

from distkeras.networking import connect
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

## BEGIN Abstract job definition. ##############################################

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

        print("Collecting daemons")
        # Allocate a port which handles the negotiation with the controller daemon.
        fd, port = allocate_tcp_listening_port()
        # Obtain the host address,
        host_address = determine_host_address()
        # Broadcast the job announcement.
        self.broadcast_job_announcement(host_address, port)
        # Wait for the daemons to connect, and supply their connection information.
        fd.settimeout(0.5)
        attempts = 0
        while attempts <= 2:
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

## END Abstract job definition. ################################################

## BEGIN Job definitions. ######################################################

class DataTransferJob(Job):
    """A class which describes a data transfer job.

    This job will transfer the data to all available daemons.
    """

    IDENTIFIER = 'data-transfer'
    TRANSFER_CHUNKS = 65536

    def __init__(self, path_source, path_destination):
        Job.__init__(self)
        # Specify job specific parameters.
        self.path_source = path_source
        self.path_destination = path_destination
        # Holds the socket which is connected with the process.
        self.socket = None
        # List container process information, same structure as daemons.
        self.processes = []
        self.processes_mutex = threading.Lock()

    def allocate_process(self, address, port):
        # Connect to the deamon process allocation service.
        fd = connect(address, port)
        # Prepare the job parameters.
        data = {}
        data['job_identifier'] = self.IDENTIFIER
        # Send the job parameters.
        send_data(fd, data)
        # Receive the address and port of the transfer process.
        data = recv_data(fd)
        description = (data['address'], data['port'])
        with self.processes_mutex:
            self.processes.append(description)
        fd.close()

    def file_path_explorer(self, path, paths):
        path = os.path.abspath(path)
        # Check if the specified path exists.
        if os.path.exists(path):
            paths.append(path)
            if os.path.isdir(path):
                contents = os.listdir(path)
                for c in contents:
                    c = os.path.abspath(path + "/" + c)
                    if os.path.isdir(c):
                        self.file_path_explorer(c, paths)
                    else:
                        paths.append(c)

    def obtain_file_paths(self):
        paths = []
        self.file_path_explorer(self.path_source, paths)

        return paths

    def create_remote_directory(self, path):
        # Specify the remote path.
        remote_path = path.replace(self.path_source, self.path_destination, 1)
        # Construct the message header.
        data = {}
        data['path'] = remote_path
        data['is_dir'] = True
        data['stop_transfer'] = False
        # Send the information.
        send_data(self.socket, data)
        # Wait for confirmation.
        response = recv_data(self.socket)
        print(response['path'] + " - " + str(response['status']))

    def transfer_file(self, path):
        # Specify the remote path.
        remote_path = path.replace(self.path_source, self.path_destination, 1)
        # Retrieve other statistics about the local file.
        file_size = os.stat(path).st_size
        header = {}
        header['path'] = remote_path
        header['is_dir'] = False
        header['stop_transfer'] = False
        header['file_size'] = file_size
        send_data(self.socket, header)
        # Check if the file is going to be created.
        response = recv_data(self.socket)
        if 'creating' in response and response['creating']:
            # Read the file, and send the buffers.
            bytes_sent = 0
            with open(path, "rb") as f:
                while bytes_sent < file_size:
                    buffer = f.read(self.TRANSFER_CHUNKS)
                    bytes_sent += len(buffer)
                    self.socket.sendall(buffer)
            # Wait for the response to check if the remote process created our file.
            response = recv_data(self.socket)
        print(response['path'] + " - " + str(response['status']))

    def stop_transfer(self):
        header = {}
        header['path'] = '/'
        header['is_dir'] = True
        header['stop_transfer'] = True
        send_data(self.socket, header)

    def transfer(self, address, port):
        # Connect with the remote process.
        fd = connect(address, port, disable_nagle=False)
        self.socket = fd
        file_paths = self.obtain_file_paths()
        # Send the files to the remote process.
        for f in file_paths:
            if os.path.isdir(f):
                self.create_remote_directory(f)
            else:
                self.transfer_file(f)
        # Stop the transfer.
        self.stop_transfer()
        # Close the file descriptor.
        fd.close()

    def run(self):
        daemons = self.collect_daemons()
        threads = []
        # Allocate a client process on all daemons.
        for d in daemons:
            # Fetch the address and port of the daemon.
            address = d[0] # Address
            port = d[1]    # Port
            # Allocate a thread which is responsible for the thread allocation.
            t = threading.Thread(target=self.allocate_process, args=(address, port))
            t.start()
            threads.append(t)
        # Wait for the process allocation to finish.
        for t in threads:
            t.join()
        del threads[:]
        # Start the transfer jobs.
        for p in self.processes:
            # Fetch the process address and port.
            p_address = p[0]
            p_port = p[1]
            # Start the transfer thread.
            t = threading.Thread(target=self.transfer, args=(p_address, p_port))
            t.start()
            threads.append(t)
        # Wait for transfer completion.
        for t in threads:
            t.join()

## END Job definitions. ########################################################
