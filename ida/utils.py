#######################################################################################################################
# Copyright (C) 2016  Regents of the University of California
#
# This is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License (GNU GPL) as published by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# A copy of the GNU General Public License can be found in LICENSE.TXT in the root of the source code repository.
# Additionally, it can be found at http://www.gnu.org/licenses/.
#
# NOTES: Per GNU GPLv3 terms:
#   * This notice must be kept in this source file
#   * Changes to the source must be clearly noted with date & time of change
#
# If you use this software in a product, an explicit acknowledgment in the product documentation of the contribution
# by Project IDA, Institute of Geophysics and Planetary Physics, UCSD would be appreciated but is not required.
#######################################################################################################################
import calendar
import os.path
import sys
import shutil
import subprocess
import glob
import tempfile
from pathlib import Path

from fabulous.color import red, bold


def pimseed(sta, i10_fn, ms_fn):

    if not (os.path.exists(i10_fn) and os.path.isfile(i10_fn)):
        print(red(bold('Error running imseed: IDA10 file not found: ' + i10_fn)))
    elif not shutil.which('imseed'):
        print(red(bold('Error running imseed: IMSEED binary not found in PATH.')))
    else:
        cmdstr = 'imseed sta=' + sta.upper() + ' < ' + i10_fn + ' > ' + ms_fn
        res = subprocess.run(cmdstr, shell=True, stderr=subprocess.PIPE, universal_newlines=True)
        if res.returncode != 0:
            print(red(bold(res.stderr)))


def i10get(sta, chan_list, startime, endtime, outfn=None, **kwargs):

    # get list of raw yr/day dirs for sta within tart/end dates
    arcrawdir = os.getenv('IDA_ARCHIVE_RAW_DIR')
    if not arcrawdir:
        print(red(bold('FATAL ERROR: IDA_ARCHIVE_RAW_DIR env var not set.')), file=sys.stderr)
        sys.exit(1)

    gz_dirs = arc_raw_i10_dirs(arcrawdir, sta.lower(), startime, endtime)

    # keep track of gz files across days for each station to remove dupes
    gz_files_processed = set()

    for gz_dir in gz_dirs:
        gz_files = set([Path(gz_file).name for gz_file in
                        (glob.glob(os.path.join(gz_dir, '*.gz')) + glob.glob(os.path.join(gz_dir, '*.GZ')))])

        # remove any already processed gz files from this batch
        gz_files -= gz_files_processed
        # add this batch to list of processed
        gz_files_processed |= gz_files

        gz_file_paths = [os.path.join(gz_dir, gz_file) for gz_file in gz_files]
        if gz_file_paths:

            if outfn:
                cmdstr = 'cat {} | gunzip | idagrep rev=10 keep={} >> {} '.format(' '.join(gz_file_paths),
                                                                                  chan_list,
                                                                                  outfn)
            else:
                cmdstr = 'cat {} | gunzip | idagrep rev=10 keep={}'.format(' '.join(gz_file_paths),
                                                                                  chan_list)

            res = subprocess.run(cmdstr, shell=True, stderr=subprocess.PIPE, universal_newlines=True)
            if res.returncode != 0:
                print(red(bold(res.stderr)))
                sys.exit(1)


def mstrim(starttime=None, endtime=None, infn=None, outfn=None):

    from obspy import UTCDateTime

    if not starttime and not endtime:
        print(red(bold('ERROR: You must supply startime, endtime or both')), file=sys.stderr)

    start_dt = UTCDateTime(starttime) if starttime else None
    end_dt = UTCDateTime(endtime) if endtime else None

    # with open(sys.__stdin__, 'rb') as msin:
    # strm_bytes = sys.__stdin__.read()

    ntf = tempfile.NamedTemporaryFile(delete=False)

    with os.fdopen(sys.stdin.fileno(), 'rb') as input_file, \
            open(ntf.name, 'wb') as output_file:
        shutil.copyfileobj(input_file, output_file)

        # for trimmed ms file
        mstmp = tempfile.NamedTemporaryFile(delete=False)  # for writeing stream to

        from obspy import read
        msfn = ntf.name
        strm = read(msfn)
        strm.trim(starttime=start_dt, endtime=end_dt)
        strm.write(mstmp.name, format='MSEED')
        del strm

        res = subprocess.run('cat ' + mstmp.name, shell=True)
        if res.returncode != 0:
            print(red(bold('ERROR streaming miniseed data to stdout.')), file=sys.stderr)

        os.remove(ntf.name)
        os.remove(mstmp.name)


def arc_raw_i10_dirs(raw_root_dir, sta, start_dt, end_dt):
    """ Returns a list of fully qualified gz sta/year/day dir names having data between start_t and end_t inclusive"""

    start_year = start_dt.year
    start_jday = int(start_dt.strftime('%j'))
    end_year = end_dt.year
    end_jday = int(end_dt.strftime('%j'))

    gz_filelist = []

    sta_dir = os.path.join(raw_root_dir, sta)
    if os.path.exists(sta_dir) and os.path.isdir(sta_dir):

        for yr in range(start_year, end_year + 1):

            if yr == start_year:
                start_day = start_jday
            else:
                start_day = 1
            if yr == end_year:
                end_day = end_jday
            else:
                end_day = 365
                if calendar.isleap(yr): end_day += 1

            for dy in range(start_day, end_day + 1):
                gz_dir = os.path.join(raw_root_dir, sta, str(yr), '{:0>3}'.format(dy))
                if os.path.exists(gz_dir) and os.path.isdir(gz_dir):
                    gz_filelist.append(os.path.join(gz_dir))

    return gz_filelist


