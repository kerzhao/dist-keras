"""Development script to deploy jobs using controller daemons."""

## BEGIN Imports. ##############################################################

from distkeras.native.jobs import Job
from distkeras.native.jobs import DataTransferJob

## END Imports. ################################################################

job = DataTransferJob("/home/joeri/experiments", "/home/joeri/experiments_nieuw")
job.run()
