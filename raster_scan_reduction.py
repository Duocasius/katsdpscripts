#!/usr/bin/python
# Reduces raster scan data and plots using scape. Data must be local.

import scape
import pylab as pl
import os
import sys
import katuilib as katui
from optparse import OptionParser

parser = OptionParser(usage="%prog [options] [<data file>]\n\n" +
                            "Reduces raster scan data and plots using scape. Use specified file or latest local data file.")
(opts, args) = parser.parse_args()

if len(args) > 0:
    data_file = args[0]
else:
    # get latest file from data dir
    data_file = ""
    p = os.listdir(katui.defaults.kat_directories["data"])
    # p.sort(reverse=True)
    while p:
        x = p.pop() # pops off the bottom of the list
        if x.endswith(".h5"):
            data_file = katui.defaults.kat_directories["data"] + "/" + x
            break

print "Reducing data file",data_file

d = scape.DataSet(data_file)
d = d.select(labelkeep="scan")

pl.figure()
pl.title("Compound scan in time - pre averaging and fitting")
scape.plot_compound_scan_in_time(d.compscans[0])

d.average()
d.fit_beams_and_baselines()

pl.figure()
pl.title("Compound scan on target with fitted beam")
scape.plot_compound_scan_on_target(d.compscans[0])

pl.figure()
pl.title("Compound scan in time - post averaging and fitting")
scape.plot_compound_scan_in_time(d.compscans[0])

pl.show()
raw_input("Hit enter to finish.")
sys.exit()