#!/usr/bin/python
#
# This examines all noise diode firings in an HDF5 file and compares the timestamp
# of each firing with one derived from the rise in recorded power.
#
# Ludwig Schwardt
# 8 February 2011
#

import time
import optparse
import sys

import numpy as np
import h5py

parser = optparse.OptionParser(usage="%prog [opts] <file>",
                               description="This checks the noise diode timing in the given HDF5 file.")
parser.add_option('-f', '--freq-chans', default='100,400',
                  help="Range of frequency channels to use (zero-based, specified as 'start,end', default %default)")
parser.add_option('-o', '--max-offset', type='float', default=2.,
                  help="Maximum allowed offset between CAM and DBE timestamps, in seconds (default %default)")
parser.add_option('-d', '--max-duration', type='float', dest='max_onoff_segment_duration', default=0.,
                  help="Maximum duration of segments around jump used to estimate instant, in seconds (default 1 dump)")
parser.add_option('-m', '--margin', type='float', dest='margin_factor', default=24.,
                  help="Allowed variation in power, as multiple of theoretical standard deviation (default %default)")
parser.add_option('-s', '--significance', type='float', dest='jump_significance', default=10.,
                  help="Keep jumps that are bigger than margin by this factor (default %default)")

(opts, args) = parser.parse_args()
if len(args) < 1:
    print 'Please specify an HDF5 file to check'
    sys.exit(1)

start_chan, end_chan = [int(n) for n in opts.freq_chans.split(',')]
sensors = {'pin' : 'rfe3_rfe15_noise_pin_on',
           'coupler' : 'rfe3_rfe15_noise_coupler_on'}

f = h5py.File(args[0], 'r')

input_map = f['Correlator']['input_map'].value
dbestr_to_corr_id = dict(zip(input_map['dbe_inputs'], input_map['correlator_product_id']))
# Number of real normal variables squared and added together
dof = 2 * f['Correlator'].attrs['accum_per_int'] * (end_chan + 1 - start_chan)

def contiguous_cliques(x, step=1):
    """Partition *x* into contiguous cliques, where elements in clique differ by *step*."""
    if len(x) == 0:
        return []
    cliques, current, prev = [], [x[0]], x[0]
    for n in x[1:]:
        if n == prev + step:
            current.append(n)
        else:
            cliques.append(current)
            current = [n]
        prev = n
    cliques.append(current)
    return cliques

def ratio_stats(mean_num, std_num, mean_den, std_den):
    """Approximate second-order statistics of ratio of uncorrelated normal variables."""
    # Transform num/den to standard form (a + x) / (b + y), with x and y uncorrelated standard normal vars
    a, b = mean_num, mean_den / std_den
    sign_h = 2 * (a >= 0) * (b >= 0) - 1
    h = sign_h * std_num
    a, r = a / h, std_den / h
    # Calculate the approximate mean and standard deviation of (a + x) / (b + y) a la F-distribution
    mean_axby = a * b / (b**2 - 1)
    std_axby = np.abs(b) / (b**2 - 1) * np.sqrt((a**2 + b**2 - 1) / (b**2 - 2))
    return mean_axby / r, std_axby / np.abs(r)

def find_jumps(timestamps, power, std_power):
    """Find significant jumps in power and estimate the time instant of each jump."""
    # Margin within which power is deemed to be constant (i.e. expected variation of power)
    margin = opts.margin_factor * std_power
    upper, lower = power + margin, power - margin
    delta_power = np.r_[power[1:], power[-1]] - np.r_[power[0], power[:-1]]
    # Shifted versions of the upper and lower power bounds
    previous_upper, next_upper = np.r_[upper[0], upper[:-1]], np.r_[upper[1:], upper[-1]]
    previous_lower, next_lower = np.r_[lower[0], lower[:-1]], np.r_[lower[1:], lower[-1]]
    # True for each power value that is considered to be the same as the one on its left
    same_as_previous = ((power > previous_lower) & (power < previous_upper)).tolist()
    same_as_previous[0] = False
    same_as_next = ((power > next_lower) & (power < next_upper)).tolist()
    same_as_next[-1] = False
    jumps = []
    # Look for significant rises in power, and pick midpoint of jump
    rise = np.where((power > previous_upper) & (power < next_upper))[0].tolist()
    for clique in contiguous_cliques(rise):
        if (len(clique) == 1) or ((len(clique) == 2) and (delta_power[clique[0]] > delta_power[clique[1]])):
            if (clique[0] not in (0, len(power) - 1)) and \
               delta_power[clique[0]] / margin[clique[0]] > opts.jump_significance:
                jumps.append(clique[0])
    # Look for significant drops in power, and pick midpoint of jump
    drop = np.where((power < previous_lower) & (power > next_lower))[0].tolist()
    for clique in contiguous_cliques(drop):
        if (len(clique) == 1) or ((len(clique) == 2) and (delta_power[clique[0]] < delta_power[clique[1]])):
            if (clique[0] not in (0, len(power) - 1)) and \
               -delta_power[clique[0]] / margin[clique[0]] > opts.jump_significance:
                jumps.append(clique[0])
    # Investigate each jump and determine accurate timestamp with corresponding uncertainty
    jump_time, jump_std_time, jump_size = [], [], []
    for jump in jumps:
        # Limit the range of points around jump to use in estimation of jump instant (to ensure stationarity)
        segment_range = np.abs(timestamps - timestamps[jump]) <= opts.max_onoff_segment_duration
        # Determine earliest (and last) sample to use to estimate the mean power before (and after) the jump
        before = min(np.where(segment_range)[0][0], jump - 1)
        after = max(len(segment_range) - 1 - np.where(segment_range[::-1])[0][0], jump + 1)
        before = max(jump - 1 - same_as_previous[jump - 1::-1].index(False), before)
        after = min(same_as_next.index(False, jump + 1), after)
        # Estimate power before and after jump, with corresponding uncertainty
        mean_power_before, mean_power_after = power[before:jump].mean(), power[jump + 1:after + 1].mean()
        std_power_before = np.sqrt(np.sum(std_power[before:jump] ** 2)) / (jump - before)
        std_power_after = np.sqrt(np.sum(std_power[jump + 1:after + 1] ** 2)) / (after - jump)
        # Use ratio of power differences before, at and after jump to estimate where in the dump the jump happened
        mean_num, mean_den = power[jump] - mean_power_before, mean_power_after - mean_power_before
        std_num = np.sqrt(std_power[jump] ** 2 + std_power_before ** 2)
        std_den = np.sqrt(std_power_after ** 2 + std_power_before ** 2)
        mean_subdump, std_subdump = ratio_stats(mean_num, std_num, mean_den, std_den)
        # Estimate instant of jump with corresponding uncertainty (assumes timestamps are accurately known)
        jump_time.append(mean_subdump * timestamps[jump] + (1. - mean_subdump) * timestamps[jump + 1])
        jump_std_time.append(std_subdump * (timestamps[jump + 1] - timestamps[jump]))
        jump_size.append(delta_power[jump] / margin[jump])
    return jump_time, jump_std_time, jump_size

offset_stats = {}
print 'Individual firings: timestamp | offset +/- uncertainty (magnitude of jump)'
print '--------------------------------------------------------------------------'
for ant in f['Antennas']:
    ant_group = f['Antennas'][ant]
    ant_name = ant_group.attrs['description'].split(',')[0]
    # Construct correlation product ID associated with available polarisations
    hh = dbestr_to_corr_id.get(ant_group['H'].attrs['dbe_input'] * 2) if 'H' in ant_group else None
    vv = dbestr_to_corr_id.get(ant_group['V'].attrs['dbe_input'] * 2) if 'V' in ant_group else None
    for diode_name, sensor in sensors.iteritems():
        # Ignore missing sensors or sensors with one entry (which serves as an initial value instead of real event)
        if sensor not in ant_group['Sensors'] or len(ant_group['Sensors'][sensor]) <= 1:
            continue
        # Collect all expected noise diode firings
        print "Diode:", ant_name, diode_name
        nd_timestamps = ant_group['Sensors'][sensor]['timestamp']
        nd_state = np.array(ant_group['Sensors'][sensor]['value'], dtype=np.int)
        for compscan in f['Scans']:
            for scan in f['Scans'][compscan]:
                scan_group = f['Scans'][compscan][scan]
                # Extract averaged power data and DBE timestamps
                dbe_timestamps = scan_group['timestamps'].value.astype(np.float64) / 1000.0
                if len(dbe_timestamps) < 3:
                    continue
                power = np.zeros(len(dbe_timestamps), dtype=np.float64)
                if hh is not None:
                    power += scan_group['data'][str(hh)][:, start_chan:end_chan+1].real.mean(axis=1)
                if vv is not None:
                    power += scan_group['data'][str(vv)][:, start_chan:end_chan+1].real.mean(axis=1)
                # Since I = HH + VV and not the average of HH and VV, the dof actually halves instead of doubling
                power_dof = dof if hh is None or vv is None else dof / 2
                jump_time, jump_std_time, jump_size = find_jumps(dbe_timestamps, power, power * np.sqrt(2. / power_dof))
                # Focus on noise diode events within this scan (and not on the edges of scan either)
                firings_in_scan = (nd_timestamps > dbe_timestamps[1]) & (nd_timestamps < dbe_timestamps[-1])
                for n, firing in enumerate(nd_timestamps[firings_in_scan]):
                    # Obtain closest time offset between expected firing and power jump
                    offsets = np.array(jump_time) - firing
                    # Ensure that jump is in the expected direction (up or down)
                    same_direction = (2 * nd_state[firings_in_scan][n] - 1) * np.sign(jump_size) > 0
                    if same_direction.any():
                        same_direction = np.where(same_direction)[0]
                        closest_jump = same_direction[np.argmin(np.abs(offsets[same_direction]))]
                        offset = offsets[closest_jump]
                        # Only match the jump if it is within a certain window of the expected firing
                        if np.abs(offset) < opts.max_offset:
                            std_offset, jump = jump_std_time[closest_jump], jump_size[closest_jump]
                            stats_key = ant_name + ' ' + diode_name
                            # For each diode, collect the offsets and their uncertainties
                            stats = offset_stats.get(stats_key, [])
                            offset_stats[stats_key] = stats + [(offset, std_offset)]
                            print '%s | offset %8.2f +/- %5.2f ms (magnitude of %+.0f margins)' % \
                                  (time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(firing)),
                                   1000 * offset, 1000 * std_offset, jump)
                        else:
                            print '%s | not found' % (time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(firing)),)

print
print 'Summary of offsets (DBE - CAM) per diode'
print '----------------------------------------'
for key, val in offset_stats.iteritems():
    # Change unit to milliseconds, and from an array from list
    offset_ms, std_offset_ms = 1000 * np.asarray(val).T
    mean_offset = offset_ms.mean()
    # Variation of final mean offset due to uncertainty of each measurement (influenced by integration time,
    # bandwidth, magnitude of power jump)
    std1 = np.sqrt(np.sum(std_offset_ms ** 2)) / len(std_offset_ms)
    # Variation of final mean due to offsets in individual measurements - this can be much bigger than std1 and
    # is typically due to changes in background power while noise diode is firing, resulting in measurement bias
    std2 = offset_ms.std() / np.sqrt(len(offset_ms))
    std_mean_offset = np.sqrt(std1 ** 2 + std2 ** 2)
    min_offset, max_offset = np.argmin(offset_ms), np.argmax(offset_ms)
    print '%s diode: mean %.2f +/- %.2f ms, min %.2f +/- %.2f ms, max %.2f +/- %.2f ms' % \
          (key, mean_offset, std_mean_offset, offset_ms[min_offset], std_offset_ms[min_offset],
           offset_ms[max_offset], std_offset_ms[max_offset])