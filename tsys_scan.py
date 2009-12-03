#!/usr/bin/python
# Perform Tsys scan at zenith and produce simulated signal data

import ffuilib
import time

# Build Fringe Finder configuration, as specified in user-facing config file
# The specific configuration is one that runs locally with DBE simulator included
# This connects to all the proxies and devices and queries their commands and sensors
ff = ffuilib.tbuild('cfg-local.ini', 'local_ff')

# Clean up any existing experiment
ff.dbe.req.dbe_capture_stop()
ff.ant1.req.mode('STOP')
time.sleep(0.5)

# Perform Tsys measurement at zenith
target = 'Zenith, azel, 0, 90'

# Let the data collector know about data file location and format
ff.k7w.req.output_directory(ffuilib.defaults.ff_directories["data"])
ff.k7w.req.write_hdf5(1)
# Set the target description string for the compound scan in the output file
ff.k7w.req.target(target)
# First scan will be a slew to the target - mark it as such before k7w starts
ff.k7w.req.scan_tag('slew')
# Do this BEFORE starting the DBE, otherwise no data will be captured
ff.k7w.req.capture_start()

# Correlator dump rate set to 1 Hz
ff.dbe.req.dbe_dump_rate(1)
# Stream 15 minutes of data (900 dumps) or until stop issued
ff.dbe.req.dbe_packet_count(900)
# Create a new data source labelled "stream", and send data to port 7010 (default k7w data port)
ff.dbe.req.dbe_capture_destination('stream', '127.0.0.1:7010')
# Now start emitting data on stream "stream"
ff.dbe.req.dbe_capture_start('stream')

# Let the antenna slew to the target and wait for target lock
# This will be the first scan of the compound scan, labelled 'slew'
ff.ant1.req.target(target)
ff.ant1.req.mode('POINT')
ff.ant1.wait('lock', True, 300)

# Once we are on the target, start a new scan labelled 'scan'
ff.k7w.req.scan_id(1, 'scan')
# Scan duration in seconds
time.sleep(60)

# Find out which files have been created
files = ff.k7w.req.get_current_files(tuple=True)[1][2]
print 'Data captured to', files

# Stop recording and shut down the experiment
ff.dbe.req.dbe_capture_stop('stream')
ff.k7w.req.capture_stop()
ff.disconnect()