#!/usr/bin/python
# Raster scan across a target producing scan data for signal displays and loading into scape

# Startup in different terminals:

import ffuilib as ffui
import time

# make fringe fingder connections
ff = ffui.tbuild("cfg-xdm.ini", "xdm")

# the target
tgt = ff.sources["EUTELSAT W2"].description

# cleanup any existing experiment
ff.ant1.req.mode("STOP")
time.sleep(0.5)

# set feed rotation
ff.ant1.req.antenna_rotation(-16.1)

# matrix scan

def matrix(width, steps):
    """Make a set of matrix scans."""
    az_start, az_end = - width / 2.0, width / 2.0
    el_start, el_end = - width / 2.0, width / 2.0
    az_step = float(width) / steps
    el_step = float(width) / steps

    az = az_start
    sign = 1
    while az <= az_end:
        yield (az, el_start*sign, az, el_end*sign)
        az += az_step
        sign = -sign

    el = el_start
    sign = 1
    while el <= el_end:
        yield (az_start*sign, el, az_end*sign, el)
        el += el_step
        sign = -sign

scans = list(matrix(1.0, 6))
scan_duration = 300

# send this target to the antenna. No time offset
ff.ant1.req.target(tgt)
ff.ant1.req.offset_fixed(-0.2, -0.3)
ff.ant1.req.mode("POINT")

# once we are on the target begin a new compound scan
# (compound scan 0 will be the slew to the target, default scan tag is "slew")
ff.ant1.wait("lock", True, 300)

print "=== Scans ==="
for i, scan in enumerate(scans):
    print i, scan

print "=== Scanning ==="
for i, scan in enumerate(scans):
    print "Scan Progress:", int((float(i) / len(scans))*100), "%"

    ff.ant1.req.scan_asym(scan[0], scan[1], scan[2], scan[3], scan_duration)
    ff.ant1.wait("lock", True, 300)

    ff.ant1.req.mode("SCAN")
    ff.ant1.wait("scan_status", "after", scan_duration + 30)

print "Scan complete."

quit()