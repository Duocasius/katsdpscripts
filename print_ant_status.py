#!/usr/bin/python

import ffuilib as ffui
import time
import sys
from optparse import OptionParser

if __name__ == "__main__":

    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage)

    parser.add_option('-a', '--antenna', dest='ant', type="string", default="ant1", metavar='ANTENNA',
                      help='antenna proxy to attach to (default="%default") as per the rc file')
    parser.add_option('-c', '--config', dest='rcfile', type="string", default="ffuilib.ant_only.rc", metavar='CONF',
                      help='ffuilib rc file for config in /var/kat/conf (default="%default")')
    (opts, args) = parser.parse_args()

    ff = ffui.cbuild(opts.rcfile)
    ant  = ff.__dict__[opts.ant] # some Simon magic
    
    state = ["|","/","-","\\"]
    period_count = 0
    print "\n"
    try:
        while True:
            lock = ant.sensor_lock.value == '1' and 'True' or 'False'
            mode = ant.sensor_mode.value
            scan = ant.sensor_scan_status.value
            desired_az = float(ant.sensor_pos_request_scan_azim.value)
            desired_el = float(ant.sensor_pos_request_scan_elev.value)
            desired_ra = float(ant.sensor_pos_request_base_ra.value)
            desired_dec = float(ant.sensor_pos_request_base_dec.value)
            actual_az = float(ant.sensor_pos_actual_scan_azim.value)
            actual_el = float(ant.sensor_pos_actual_scan_elev.value)
            error_az = abs(actual_az - desired_az)
            error_el = abs(actual_el - desired_el)
            status = "\r%s: %s Time:%s  Mode:\033[34m%s\033[0m Scan:\033[34m%s\033[0m Lock:\033[34m%s\033[0m  Base[Ra:\033[32m%.2F\033[0m Dec:\033[32m%.2F\033[0m] Req[Az:\033[32m%.2F\033[0m El:\033[32m%.2F\033[0m]  Act[Az:\033[33m%.2F\033[0m El:\033[33m%.2F\033[0m]  Err[Az:\033[31m%.2F\033[0m El:\033[31m%.2F\033[0m]" % (opts.ant, state[period_count % 4], time.ctime().split(" ")[3], mode, scan, lock, desired_ra, desired_dec, desired_az, desired_el, actual_az, actual_el, error_az, error_el)

            sys.stdout.write(status)
            sys.stdout.flush()
            period_count += 1
            time.sleep(0.5)
    except Exception,err:
        print "Error: Disconnecting... (",err,")"
        ff.disconnect()
    except KeyboardInterrupt:
        print "\nDisconnecting..."
        ff.disconnect()
    print "Done."