"""Daemon module.

Describes all functionality of a ML job daemon scheduler.
Basically, a Daemon in a dist-keras context is responsible for the
allocation of certain resources. Think of it as an easy way to allocate
specific algorithms on different machines, without having the burden to
SSH and copy files to those machines. Furthermore, the deamons are responsible
to bring the trainers in direct contact with the parameter servers and workers
for additional training metrics."""

## BEGIN Imports. ##############################################################

from distkeras.networking import connect
from distkeras.networking import recv_data
from distkeras.networking import send_data

import os

## END Imports. ################################################################
