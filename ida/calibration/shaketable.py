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
from datetime import datetime
import os
from os.path import exists, join, isfile  #  , abspath, split, isdir
#from pathlib import Path
import yaml
import collections
import logging

from numpy import float32, logical_and, less_equal, greater_equal, greater, \
    polyfit, polyval, subtract, log10, ceil, floor
from numpy.fft import rfft, irfft
import matplotlib
matplotlib.use('Qt4Agg')
import matplotlib.pyplot as plt
plt.ion()

from fabulous.color import red, bold
from obspy.core import read, Stream, UTCDateTime
from obspy.signal.invsim import evalresp

from ida.calibration.cross import cross_correlate

def rename_chan(inchan):

    bhz_chan_list = ['UN1', 'BHZ', 'HHZ', 'HNZ']
    bhn_chan_list = ['UN2', 'BHN', 'HHN', 'HHY', 'HNY', 'BH1']
    bhe_chan_list = ['UN3', 'BHE', 'HHE', 'HHX', 'HNX', 'BH2']

    if inchan in bhz_chan_list:
        return 'BHZ'
    elif inchan in bhn_chan_list:
        return 'BH1'
    elif inchan in bhe_chan_list:
        return 'BH2'
    else:
        return inchan

def correlate_channel_traces(chan_trace, ref_trace, sample_rate, shake_m_per_volt, digi_sens_cnts_per_volt, **kwargs):

    cross_results = {}
    npts = ref_trace.stats.npts
    # comp = chan_trace.stats.channel[2]
    # ref_comp = ref_trace.stats.channel[2]
    # thedate = chan_trace.stats.starttime
    if not os.environ.get('SEEDRESP'):
        print(red('Error: Can not find RESP files without SEEDRESP env var being set.'))
        return False, cross_results
    else:
        resp_dir = os.environ.get('SEEDRESP')

    # construct RESP file filename for ref_trace
    resp_file = 'RESP.{}.{}.{}.{}'.format(
        ref_trace.stats.network,
        ref_trace.stats.station,
        ref_trace.stats.location,
        ref_trace.stats.channel
    )
    resp_filepath = join(resp_dir, resp_file)

    fresp, f = evalresp(1/sample_rate,
                        ref_trace.stats.npts,
                        resp_filepath,
                        ref_trace.stats.starttime,
                        station=ref_trace.stats.station,
                        channel=ref_trace.stats.channel,
                        network=ref_trace.stats.network,
                        locid=ref_trace.stats.location,
                        units='DIS', freq=True )

    # Convolving ref data with nominal response...
    refdata    = ref_trace.data.astype(float32)
    mean       = refdata.mean()
    refdata   -= mean
    refdata_fft    = rfft(refdata)
    refdata_fft   *= fresp
    ref_wth_resp  = irfft(refdata_fft, npts)
    ref_wth_resp *= (shake_m_per_volt/digi_sens_cnts_per_volt)

    # trim 20 smaples off both ends.
    ref_wth_resp = ref_wth_resp[20:-20]
    outdata = chan_trace.data[20:-20].astype(float32)

#    if 'smoothing_factor' in kwargs:
#        sf = kwargs['smoothing_factor']
#    else:
#        sf = 0.5
    sf = kwargs.get('smoothing_factor', 0.5)
    # noinspection PyTupleAssignmentBalance
    freqs, amp, pha, coh, psd1, psd2, _, _, _ = cross_correlate(sample_rate,
                                                                outdata,
                                                                ref_wth_resp, smoothing_factor=sf)

    cross_results = {
        'freqs': freqs,
        'amp': amp,
        'pha': pha,
        'coh': coh,
        'psd1': psd1,
        'psd2': psd2,
        'cospect': [],
        'quadspect': [],
    }

    return cross_results

def shake_table_chan_plots(datadir, comp, cross_res_dict, coh_min=0.98, freq_band=(0.1, 10)):

    freqs = cross_res_dict['freqs']
    amp = cross_res_dict['amp']
    pha = cross_res_dict['pha']
    coh = cross_res_dict['coh']
    psd1 = cross_res_dict['psd1']
    psd2 = cross_res_dict['psd2']

    # get ndxs of good coh in freq_band
    use_freqs = logical_and(less_equal(freqs, freq_band[1]), greater_equal(freqs, freq_band[0]))

    fr = freqs[use_freqs]
    co = coh[use_freqs]
    ps1 = psd1[use_freqs]
    ps2 = psd2[use_freqs]
    am = amp[use_freqs]
    ph = pha[use_freqs]

    # comp = 'Z'
    fig_ndx = 0
    if comp == 'BHZ':
        fig_ndx = 0
    elif comp == 'BH1':
        fig_ndx = 10
    elif comp == 'BH2':
        fig_ndx = 30

    # plot psd for both time series
    fig1 = plt.figure(fig_ndx + 1, figsize=(8.5, 11))
    plt.subplot(311)
    plt.title('Fig 1: {} : {}'.format(datadir, comp))
    plt.suptitle('Big Title')
    plt.xlim(1e-1, 10)
    # plt.ylim(75, 110)
    plt.ylabel('PSD (dB)')
    plt.xlabel('Freq (Hz)')
    plt.grid(which='both')
    plt.semilogx(fr, 10 * log10(ps1))
    plt.semilogx(fr, 10 * log10(ps2))

    plt.subplot(312)
    plt.xlim(1e-1, 10)
    plt.ylim(0.97, 1.01)
    plt.ylabel('Coh**2')
    plt.xlabel('Freq (Hz)')
    plt.grid(which='both')
    plt.semilogx(fr, co)

    fig2 = plt.figure(fig_ndx + 2, figsize=(8.5, 11))
    plt.subplot(311)
    plt.title('Fig 2: {} : {}'.format(datadir, comp))
    plt.xlim(1e-1, 10)
    # plt.ylim(0.99, 1.01)
    plt.ylabel('TF Gain')
    plt.xlabel('Freq (Hz)')
    plt.grid(which='both')
    plt.semilogx(fr, am)

    plt.subplot(312)
    plt.xlim(1e-1, 10)
    plt.ylim(-10, 5)
    plt.ylabel('TF Phase')
    plt.xlabel('Freq (Hz)')
    plt.grid(which='both')
    plt.semilogx(fr, ph)

    plt.subplot(313)
    plt.xlim(1e-1, 10)
    plt.ylim(0.97, 1.01)
    plt.xlabel('Freq (Hz)')
    plt.ylabel('Coh**2')
    plt.grid(which='both')
    plt.semilogx(fr, co)

    # now just coh >= coh_min
    good_coh = greater(co, coh_min)
    fr = fr[good_coh]
    am = am[good_coh]
    ph = ph[good_coh]
    co = co[good_coh]

    # and remove trend/time shift from phase
    coeffs = polyfit(fr, ph, 1)
    # set y-intercept to 0
    coeffs = (coeffs[0], 0)
    correction = polyval(coeffs, fr)
    ph = subtract(ph, correction)

    fig3 = plt.figure(fig_ndx + 3, figsize=(8.5, 11))
    plt.subplot(311)
    plt.title('Fig 3: {} : {}'.format(datadir, comp))
    plt.xlim(1e-1, 10)
    # plt.ylim(0.99, 1.01)
    plt.ylabel('TF Gain')
    plt.xlabel('Freq (Hz)')
    plt.grid(which='both')
    plt.semilogx(fr, am)

    plt.subplot(312)
    plt.xlim(1e-1, 10)
    # plt.ylim(-10, 5)
    plt.ylabel('TF Phase')
    plt.xlabel('Freq (Hz)')
    plt.grid(which='both')
    plt.semilogx(fr, ph)

    plt.subplot(313)
    plt.xlim(1e-1, 10)
    plt.ylim(0.97, 1.01)
    plt.xlabel('Freq (Hz)')
    plt.ylabel('Coh**2')
    plt.grid(which='both')
    plt.semilogx(fr, co)

    return fig1, fig2, fig3

def shake_table_psd_plot(fignum, datadir, comp, freqs, psd1, psd2, coh, add_title_text=''):

    # plot psd for both time series
    fig = plt.figure(fignum, figsize=(8.5, 11))
    plt.subplot(311)
    plt.title('Shake Table PSDs: {} : {}'.format(datadir, comp) + add_title_text)
    plt.xlim(1e-1, 10)
    # plt.ylim(75, 110)

    plt.ylabel('PSD (dB)')
    plt.xlabel('Freq (Hz)')
    plt.grid(which='both')
    plt.semilogx(freqs, 10 * log10(psd1))
    plt.semilogx(freqs, 10 * log10(psd2))

    plt.subplot(312)
    plt.xlim(1e-1, 10)
    plt.ylim(0.9, 1.01)
    plt.ylabel('Coh**2')
    plt.xlabel('Freq (Hz)')
    plt.grid(which='both')
    plt.semilogx(freqs, coh)

    return fig

def shake_table_tf_plot(fignum, datadir, comp, freqs, amp, pha, coh, add_title_text=''):

    fig = plt.figure(fignum, figsize=(8.5, 11))
    plt.subplot(311)
    plt.title('Shake Table TF: {} : {}'.format(datadir, comp) + add_title_text)
    plt.xlim(1e-1, 10)
    plt.ylim(floor(amp.min() * 100) / 100, ceil(amp.max() * 100) / 100)
#    axlim = plt.axis()

    plt.ylabel('TF Gain')
    plt.xlabel('Freq (Hz)')
    plt.grid(which='both')
    plt.semilogx(freqs, amp)

    plt.subplot(312)
    plt.xlim(1e-1, 10)
    # plt.ylim(-10, 5)
    plt.ylabel('TF Phase')
    plt.xlabel('Freq (Hz)')
    plt.grid(which='both')
    plt.semilogx(freqs, pha)

    plt.subplot(313)
    plt.xlim(1e-1, 10)
    plt.ylim(0.9, 1.01)
    plt.xlabel('Freq (Hz)')
    plt.ylabel('Coh**2')
    plt.grid(which='both')
    plt.semilogx(freqs, coh)

    return fig

class ShakeConfig(object):

    # for cleanup of (mostly) past crud.
    bhz_chan_list = ['UN1', 'BHZ', 'HHZ', 'HNZ']
    bhn_chan_list = ['UN2', 'BHN', 'HHN', 'HHY', 'HNY', 'BH1']
    bhe_chan_list = ['UN3', 'BHE', 'HHE', 'HHX', 'HNX', 'BH2']

    def __init__(self, fn, shaketable_subdir='shaketable', debug=False, logger=None):

        self.ok = True

        if not logger:
            self.logger = logging.getLogger('ShakeTable')
            # set up wARN/ERROR handler
            fmtr = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s: %(message)s')
            hndlr = logging.StreamHandler()
            hndlr.setFormatter(fmtr)
            # set up log level
            if debug:
                hndlr.setLevel(logging.DEBUG)
            else:
                hndlr.setLevel(logging.WARN)
            self.logger.addHandler(hndlr)
        else:
            self.logger = logger

        self.shaketable_subdir = shaketable_subdir

        self.stream = None
        self.traces = {}

        self._config = yaml.load('')
        with open(fn, 'rt') as cfl:
            config_txt = cfl.read()
        try:
            self._config = yaml.load(config_txt)
        except:
            self._config = {}
            self.logger.error('Error parsing YAML config file: ', fn)
            self.ok = False
        else:
            self._process_config()

    def _process_config(self):

        # check ENV
        if not os.environ.get('IDA_CAL_RAW_DIR'):
            self.logger.error('The env var IDA_CAL_RAW_DIR must be set.')
            self.ok = False
        if not os.environ.get('IDA_CAL_ANALYSIS_DIR'):
            self.logger.error('The env var IDA_CAL_ANALYSIS_DIR must be set.')
            self.ok = False
        if not os.environ.get('SEEDRESP'):
            self.logger.error('The env var SEEDRESP must be set.')
            self.ok = False

        if 'shaketable_ms_filename' not in self._config:
            self.ok = False
            self.logger.error('Missing entry in configuration file: ' +
                              'shaketable_ms_filename must contain the ' + 
                              ' path the shake table miniseed file relative to ' +
                              os.environ.get('IDA_CAL_RAW_DIR') + '/shaketable.')
        else:
            data_path = os.path.abspath(os.path.join(
                os.environ.get('IDA_CAL_RAW_DIR', ''),
                'shaketable',
                self._config['shaketable_ms_filename']))
            if not isfile(data_path) or not exists(data_path):
                self.logger.error('Miniseed file {} not found.'.format(data_path))
                self.ok = False
            else:
                self.ms_filename = data_path
                self.data_dir = os.path.dirname(data_path).split(os.sep)[-1]
                print(self.ms_filename)
                print(self.data_dir)

        if 'analysis_sample_rate' not in self._config:
            self.ok = False
            self.logger.error('Missing entry in configuration file: ' + 'sample_rate')
        if 'digi_cnts_per_volt' not in self._config:
            self.ok = False
            self.logger.error('Missing entry in configuration file: ' + 'digi_cnts_per_volt')
        if 'shaketable_hori_resp' not in self._config:
            self.ok = False
            self.logger.error('Missing entry in configuration file: ' + 'shaketable_hori_resp')
        else:
            if not isinstance(self._config['shaketable_hori_resp'], list):
                self.ok = False
                self.logger.error('Missing entry in configuration file: ' +
                                  'shaketable_hori_resp must contain a list.')
            else:
                if 'startdate' not in self._config['shaketable_hori_resp'][0]:
                    self.ok = False
                    self.logger.error('Missing entry in configuration file: ' +
                                'shaketable_hori_resp/startdate')
                if 'enddate' not in self._config['shaketable_hori_resp'][0]:
                    self.ok = False
                    self.logger.error('Missing entry in configuration file: ' +
                                'shaketable_hori_resp/enddate')
                if 'meters_per_volt' not in self._config['shaketable_hori_resp'][0]:
                    self.ok = False
                    self.logger.error('Missing entry in configuration file: ' +
                                'shaketable_hori_resp/meters_per_volt')

        if 'shaketable_vert_resp' not in self._config:
            self.ok = False
            self.logger.error('Missing entry in configuration file: ' + 'shaketable_vert_resp')
        else:
            if not isinstance(self._config['shaketable_vert_resp'], list):
                self.ok = False
                self.logger.error('Missing entry in configuration file: ' +
                                  'shaketable_vert_resp must contain a list.')
            else:
                if 'startdate' not in self._config['shaketable_vert_resp'][0]:
                    self.ok = False
                    self.logger.error('Missing entry in configuration file: ' +
                                'shaketable_vert_resp/startdate')
                if 'enddate' not in self._config['shaketable_vert_resp'][0]:
                    self.ok = False
                    self.logger.error('Missing entry in configuration file: ' +
                                'shaketable_vert_resp/enddate')
                if 'meters_per_volt' not in self._config['shaketable_vert_resp'][0]:
                    self.ok = False
                    self.logger.error('Missing entry in configuration file: ' +
                                'shaketable_vert_resp/meters_per_volt')

        if 'plot_settings' not in self._config:
            self.ok = False
            self.logger.error('Missing entry in configuration file: ' + 'plot_settings')
        if 'smoothing_factor' not in self._config:
            self.ok = False
            self.logger.error('Missing entry in configuration file: ' + 'smoothing_factor')
        if 'coherence_cutoff' not in self._config:
            self.ok = False
            self.logger.error('Missing entry in configuration file: ' + 'coherence_cutoff')

    @property
    def sample_rate(self):
        return self._config['analysis_sample_rate']

    @property
    def table_h_resp(self):
        return self._config['shaketable_hori_resp']

    @property
    def table_v_resp(self):
        return self._config['shaketable_vert_resp']

    @property
    def plot_min_freq(self):
        return self._config['plot_settings']['start_freq']

    @property
    def plot_max_freq(self):
        return self._config['plot_settings']['end_freq']

    @property
    def coherence_cutoff(self):
        return self._config['coherence_cutoff']

    @property
    def smoothing_factor(self):
        return self._config['smoothing_factor']

    @property
    def components(self):
        return self._config['components']

    @property
    def ref_sensor_network(self):
        return self._config.get('ref_sensor_network', 'UNK')

    @property
    def ref_sensor_station(self):
        return self._config.get('ref_sensor_station', 'NA')

    def digi_cnts_per_volt(self, digi_sn=None):
        return self._config['digi_cnts_per_volt']

    def shake_table_meters_per_volt(self, comp, thedate, shaketable_sn=None):

        if comp.upper() not in ['Z', '1', '2']:
            raise ValueError('Invalid component: ', comp)

        # noinspection PyUnresolvedReferences
        if not isinstance(thedate, datetime):
            raise TypeError('Invalid date: ' + str(thedate))

        dt = int(thedate.strftime('%Y%j'))

        res = 0
        if comp.upper() == 'Z':
            periods = [p for p in self.table_v_resp if (dt>=p['startdate']) and (dt<=p['enddate'])]
            if periods:
                res = periods[0]['meters_per_volt']
        else:
            periods = [p for p in self.table_h_resp if (dt>=p['startdate']) and (dt<=p['enddate'])]
            if periods:
                res = periods[0]['meters_per_volt']

        return res

    def read_msfile(self):

        if exists(self.ms_filename) and isfile(self.ms_filename):
            try:
                self.stream = read(self.ms_filename)
            except:
                print(red(bold('Error reading miniseed file: ' + self.ms_filename)))
            else:
                for tr in self.stream:
                    tr.stats.location = tr.stats.location.rjust(2, '0')
        else:
            print('ERROR: Miniseed file does not exist: ' + self.ms_filename)

        return self.stream

    def save_chan_traces(self, fn, strm):

        try:
            strm.write(fn, format='MSEED')
        except:
            return False
        else:
            return True


    def prepare_traces(self):

        if self.stream:

            # cleanup chan codes in miniseed
            for tr in self.stream:
                if tr.stats.channel in self.bhz_chan_list:
                    tr.stats.channel = 'BHZ'
                elif tr.stats.channel in self.bhn_chan_list:
                    tr.stats.channel = 'BH1'
                elif tr.stats.channel in self.bhe_chan_list:
                    tr.stats.channel = 'BH2'
                else:
                    print(self.stream)
                    raise ValueError('Unknown channel code encoutnered: ' + tr.stats.channel)

            # loop through metadata record with trace start/end time info
            # and drop and channels without waveform 'wf' ot 'wf_ref' data
            self.traces = collections.OrderedDict()
#            for chan, vals in meta.items():
            for meta in self.components:
                chan = meta['chan'].upper()
                ref_chan = meta['ref_chan'].upper()
                try:
                    start = UTCDateTime(meta['starttime'])
                except:
                    raise ValueError('\nError parsing starttime: ' + meta['starttime'])
                try:
                    end = UTCDateTime(meta['endtime'])
                except:
                    raise ValueError('\nError parsing endtime: ' + meta['endtime'])
                wf = self.stream.select(channel=chan).copy().trim(start, end)
                wf_ref = self.stream.select(channel=ref_chan).copy().trim(start, end)
                print('CHAN:', chan, wf)
                print('REF: ', ref_chan, wf_ref)
                if wf and wf_ref:
                    # print('GOOD FOR ', chan)
                    self.traces[chan] = {}
                    self.traces[chan]['ref_chan'] = ref_chan
                    self.traces[chan]['wf'] = wf[0]
                    self.traces[chan]['wf_ref'] = wf_ref[0]
                    self.traces[chan]['wf'].stats.network = self.ref_sensor_network
                    #self.traces[chan]['wf'].stats.loc = vals['loc']
                    self.traces[chan]['wf'].stats.station = self.ref_sensor_station
                    self.traces[chan]['wf_ref'].stats.network = self.ref_sensor_network
                    #self.traces[chan]['wf_ref'].stats.loc = vals['loc']
                    self.traces[chan]['wf_ref'].stats.station = self.ref_sensor_station

                    fn = self.ref_sensor_network + '_' + self.ref_sensor_station + '_' + \
                            chan + '_' + wf[0].stats.location + '_shaketable.ms'
                    if not self.save_chan_traces(fn, Stream([wf[0], wf_ref[0]])):
                        print('Error writing shaketable traces for channel: {} to file: {}.'.format(chan, fn))
                else:
                    print(self.stream)
                    if not wf:
                        print(red('No trace in {} for channel: {} during {} - {}'.format(self.ms_filename,
                                                                                         chan,
                                                                                         meta['starttime'],
                                                                                         meta['endtime'])))
                    if not wf_ref:
                        print(red('No trace in {} for reference channel: {} during {} - {}'.format(self.ms_filename,
                                                                                                   meta['ref_chan'],
                                                                                                   meta['starttime'],
                                                                                                   meta['endtime'])))
                    return False

            return True

        else:
            raise Exception('Miniseed data not loaded. Did you call read_msfile?')

    def save_header(self, resfl, analdate):
        header = '#'*144 + '\n'
        header += '# SHAKETABLE ANALYSIS PARAMETERS\n'
        header += '# ==============================\n'
        header += '#               analysis at: {}\n'.format(analdate)
        header += '#                   dataset: {}\n'.format(self.data_dir)
        header += '#        digi cnts per volt: {}\n'.format(self.digi_cnts_per_volt())
        header += '#          sample rate (hz): {}\n'.format(self.sample_rate)
        header += '#      coh smoothing factor: {}\n'.format(self.smoothing_factor)
        header += '#                coh cutoff: {}\n'.format(self.coherence_cutoff)
        chnzinfo = self.traces['BHZ']
        header += '#       chan BHZ   ref chan: {}\n'.format(chnzinfo['ref_chan'])
        header += '#       chan BHZ start time: {}\n'.format(chnzinfo['wf'].stats.starttime)
        header += '#       chan BHZ   end time: {}\n'.format(chnzinfo['wf'].stats.endtime)
        chn1info = self.traces['BH1']
        header += '#       chan BH1   ref chan: {}\n'.format(chn1info['ref_chan'])
        header += '#       chan BH1 start time: {}\n'.format(chn1info['wf'].stats.starttime)
        header += '#       chan BH1   end time: {}\n'.format(chn1info['wf'].stats.endtime)
        chn2info = self.traces['BH2']
        header += '#       chan BH2   ref chan: {}\n'.format(chn2info['ref_chan'])
        header += '#       chan BH2 start time: {}\n'.format(chn2info['wf'].stats.starttime)
        header += '#       chan BH2   end time: {}\n'.format(chn2info['wf'].stats.endtime)

        hori_sens = self.shake_table_meters_per_volt('1', chn1info['wf'].stats.starttime.datetime)
        header += '# shake tbl hori sens (m/V): {}\n'.format(hori_sens)
        vert_sens = self.shake_table_meters_per_volt('Z', chnzinfo['wf'].stats.starttime.datetime)
        header += '# shake tbl vert sens (m/V): {}\n'.format(vert_sens)

        header += '#  plot start freq (hz): {}\n'.format(self.plot_min_freq)
        header += '#  plot   end freq (hz): {}\n'.format(self.plot_max_freq)
        header += '#\n'

        header += '#H {:<24} {:4} {:8} {:27} {:17} {:27} {:17}' \
                 '{:>7} {:>8} {:>7} {:>8} ' \
                '{:>7} {:>10} {}\n'.format(
                     'data_dir','chan', 'ref_chan',
                     'start_time', 'start_epoch', 'end_time', 'end_epoch',
                     'ampmn', 'ampstd', 'phamn', 'phastd',
                     'coh_cut', 'analyzedon', 'ms_file')
        resfl.write(header)

    def save_footer(self, resfl):
        resfl.write('#'*144 + '\n')

    def analyze(self):

# TODO: Add header to results file with all parameters
        resfn = self.data_dir + 'results.txt'
        analdate = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with open(resfn, 'at') as resfl:
            self.save_header(resfl, analdate)

        fignum = 0
        for chan, chaninfo in self.traces.items():

            wf = chaninfo['wf']
            wf_ref = chaninfo['wf_ref']
            starttime = wf.stats.starttime.datetime  # convert UTCDateTime to datetime.datetime

            cross_res = correlate_channel_traces(wf,
                                                 wf_ref,
                                                 self.sample_rate,
                                                 self.shake_table_meters_per_volt(chan[2],
                                                                                    starttime),
                                                 self.digi_cnts_per_volt(),
                                                 smoothing_factor=self.smoothing_factor)

            # get ndxs of good coh in freq_band
            min_freq = self.plot_min_freq
            max_freq = self.plot_max_freq
            use_freqs = logical_and(less_equal(cross_res['freqs'], max_freq),
                                    greater_equal(cross_res['freqs'], min_freq))

            fr = cross_res['freqs'][use_freqs]
            co = cross_res['coh'][use_freqs]
            ps1 = cross_res['psd1'][use_freqs]
            ps2 = cross_res['psd2'][use_freqs]
            am = cross_res['amp'][use_freqs]
            ph = cross_res['pha'][use_freqs]

            fignum += 1
            psd_fig = shake_table_psd_plot(fignum, self.data_dir, chan, fr, ps1, ps2, co)
            psd_fig.savefig('{}_{}_psd_fig.png'.format(chan, self.data_dir), dpi=400)

            fignum += 1
            tf_fig_1 = shake_table_tf_plot(fignum, self.data_dir, chan, fr, am, ph, co)
            tf_fig_1.savefig('{}_{}_tf_fig1.png'.format(chan, self.data_dir), dpi=400)

            # detrend and take only "good" coh points
            # now just coh >= coh_min
            coh_min = self.coherence_cutoff
            good_coh = greater(co, coh_min)
            fr = fr[good_coh]
            am = am[good_coh]
            ph = ph[good_coh]
            co = co[good_coh]

            # and remove trend/time shift from phase
            coeffs = polyfit(fr, ph, 1)
            coeffs = (coeffs[0], 0)  # set y-intercept to 0
            correction = polyval(coeffs, fr)
            ph = subtract(ph, correction)

            # construct plot with only good coh points
            fignum += 1
            tf_fig_2 = shake_table_tf_plot(fignum, self.data_dir, chan, fr, am, ph, co, 
                                           '\n(coh**2 > {}; Phase de-trended)'.format(coh_min))
            tf_fig_2.savefig('{}_{}_tf_fig2.png'.format(chan, self.data_dir), dpi=400)

            # calculate overall values to save
            amp_mn = am.mean()
            amp_std = am.std()
            pha_mn = ph.mean()
            pha_std = ph.std()

            res_txt = '   {:<24} {:4} {:8} {:27} {:17} {:27} {:17}' \
                 '{:>7} {:>8} {:>7} {:>8} ' \
                '{:>7} {:>10} {}\n'.format(
                     self.data_dir, chan, chaninfo['ref_chan'],
                     wf.stats.starttime.datetime, 'start_epoch',
                     wf.stats.endtime.datetime, 'end_epoch',
                     amp_mn, amp_std, pha_mn, pha_std,
                     self.coherence_cutoff, 'analyzedon', self.ms_filename)
            with open(resfn, 'at') as resfl:
                resfl.write(res_txt + '\n')

        with open(resfn, 'at') as resfl:
            self.save_footer(resfl)
