"""Native workers module.

Specific distributed optimizer implementations.
"""

## BEGIN Imports. ##############################################################

from distkeras.networking import connect
from distkeras.networking import recv_data
from distkeras.networking import send_data

import threading

import numpy as np

import socket

## END Imports. ################################################################
