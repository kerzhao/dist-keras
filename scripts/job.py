"""Development script to deploy jobs using controller daemons."""

## BEGIN Imports. ##############################################################

from distkeras.native.jobs import Job
from distkeras.native.jobs import DataTransferJob

## END Imports. ################################################################

job = DataTransferJob("/home/joeri/experiments", "/tmp/test")
job.add_daemon(("itrac1501.cern.ch", 7000))
job.add_daemon(("itrac1502.cern.ch", 7000))
job.run()
