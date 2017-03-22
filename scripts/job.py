"""Development script to deploy jobs using controller daemons."""

## BEGIN Imports. ##############################################################

from distkeras.native.jobs import Job

## END Imports. ################################################################

job = Job()
print(job.collect_daemons())
