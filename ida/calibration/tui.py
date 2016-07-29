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
import glob
import os
from pathlib import Path

from ida.tui import pick, pick2
from ida import IDA_CAL_RAW_DIR
from ida.signals.paz import PAZ


def select_raw_cal_staloc(staloc_stub):

    staloc_stub = staloc_stub.lower()
    staloc, staloc_full_path = None, None

    stalocdirlist = glob.glob(os.path.join(IDA_CAL_RAW_DIR, staloc_stub + '*[01][01]'))
    stalocdirlist = sorted([Path(item).stem for item in stalocdirlist])

    if stalocdirlist:
        success, ndx = pick(stalocdirlist,
                            title='Select Raw Cal Sta+Loc',
                            prompt='Select # of desired StaLoc (or "q" to quit): ',
                            allow_quit_q=True,
                            menu_on_error=True,
                            err_message='Invalid selection. Please try again.')
        if success:
            staloc = stalocdirlist[ndx]
            staloc_full_path = os.path.join(IDA_CAL_RAW_DIR, staloc)
    else:
        success = False

    return success, staloc, staloc_full_path


def select_raw_cal_sensor(station):

    station = station.lower()
    loc, sensor_model, sensor_root_dir = None, None, None

    sensordirlist = glob.glob(os.path.join(IDA_CAL_RAW_DIR, station + '??', '*'))
    sensordirlist = sorted(['/'.join(item.split(os.sep)[-2:]) for item in sensordirlist])
    # rawdirlist.append('Quit')

    if sensordirlist:
        success, ndx = pick(sensordirlist,
                            title='Sensor List for ' + station.upper(),
                            prompt='Select # of desired SENSOR (or "q" to quit): ',
                            allow_quit_q=True,
                            menu_on_error=True,
                            err_message='Invalid selection. Please try again.')
        if success:
            sensor_dir = sensordirlist[ndx]
            loc = sensor_dir.split('/')[0][-2:]
            sensor_model = sensor_dir.split(os.sep)[1]
            sensor_root_dir = os.path.join(IDA_CAL_RAW_DIR, sensor_dir)
    else:
        success = False

    return success, station, loc, sensor_model, sensor_root_dir


def select_raw_cal_date(sensor_root_dir, cal_type):

    title_dict = {'rblf': 'Low Freq',
                  'rbhf': 'High Freq'
                 }
    if not os.path.exists(sensor_root_dir):
        raise ValueError('Directory does not exist: ' + sensor_root_dir)

    date_dir, date_str = None, None

    # get date dir list
    datedirlist = glob.glob(os.path.join(sensor_root_dir, cal_type, '*'))
    datedirlist = sorted([os.sep.join(item.split(os.sep)[-2:]) for item in datedirlist])

    suc = False
    if len(datedirlist) == 0:
        suc = False
        date_str = 'No raw calibration dates found for this sensor.'

    elif len(datedirlist) > 1:
        suc, ndx = pick(datedirlist,
                        title=title_dict[cal_type] + ' dates for sensor: ' +
                              os.sep.join(sensor_root_dir.split(os.sep)[-2:]),
                        prompt='Select # of desired DATE (or "q" to quit): ',
                        allow_quit_q=True,
                        menu_on_error=True,
                        err_message='Invalid selection. Please try again.')
        if suc:
            date_dir = datedirlist[ndx]
        else:
            date_str = 'User canceled.'

    elif len(datedirlist) == 1:
        suc = True
        date_dir = datedirlist[0]

    # make full path
    if suc:
        date_str = date_dir.split(os.sep)[1]
        date_dir = os.path.join(sensor_root_dir, date_dir)

    return suc, date_str, date_dir


def select_raw_cal_files(rb_dir):

    if not os.path.exists(rb_dir):
        raise ValueError('Directory does not exist: ' + rb_dir)

    # get ms and log files and compare lists
    ms_files = sorted(glob.glob(os.path.join(rb_dir, '*.ms')))
    log_files = sorted(glob.glob(os.path.join(rb_dir, '*.log')))
    ms_stems = [Path(msfn).stem for msfn in ms_files]
    log_stems = [Path(logfn).stem for logfn in log_files]

    paired_cals = [stem for stem in ms_stems if stem in log_stems]

    rb_files = None

    if len(ms_files) == 0:
        rb_files = (None, None)
        suc = True

    elif len(ms_files) == 1:
        suc = True
        rb_files = (os.path.join(rb_dir, ms_files[0]), os.path.join(rb_dir, log_files[0]))

    else:  # need to pick
        suc, ndx = pick(paired_cals,
                        title='Miniseed files found in: ' + os.sep.join(rb_dir.split(os.sep)[-2:]),
                        prompt='Select # of the file to process (or "q" to quit): ',
                        allow_quit_q=True,
                        menu_on_error=True,
                        err_message='Invalid selection. Please try again.')
        if suc:
            rb_files = (os.path.join(rb_dir,
                                     paired_cals[ndx]+'.ms'),
                        os.path.join(rb_dir,
                                     paired_cals[ndx]+'.log'))

    return suc, rb_files


def select_perturb_map(paz):

    grp_titles = ['', 'Zeros', 'Poles']
    prompt = 'Enter comma separated list (or "q" to quit): '

    if not isinstance(paz, PAZ):
        raise TypeError('paz must be a populated PAZ object')

    paz_fit_lf = paz.make_partial2(norm_freq=1.0, partial_mode=paz.PARTIAL_FITTING_LF)
    paz_fit_hf = paz.make_partial2(norm_freq=1.0, partial_mode=paz.PARTIAL_FITTING_HF)

    poles_pert_def, zeros_pert_def = paz.perturb_defaults()
    defchoice = [('D', 'Use Defaults (indicated by "<==")')]

    # make list of LF p/z to user perturbing choices
    # Do LOW FREQ FIRST
    zero_pert_choices = []
    pole_pert_choices = []
    for ndx, val in enumerate(paz_fit_lf.zeros()):
        if ndx in zeros_pert_def[0]:
            zero_pert_choices.append(str(val) + ' <==')
        else:
            zero_pert_choices.append(str(val))
    for ndx, val in enumerate(paz_fit_lf.poles()):
        if ndx in poles_pert_def[0]:
            pole_pert_choices.append(str(val) + ' <==')
        else:
            pole_pert_choices.append(str(val))

    pert_choices = [defchoice, zero_pert_choices, pole_pert_choices]
    success, choices, pert_choice_groups = pick2(pert_choices,
                                                 'Select LOW FREQ zeros & poles to perturb',
                                                 prompt=prompt,
                                                 group_titles=grp_titles,
                                                 multiple_choice=True,
                                                 implicit_quit_q=True, menu_on_error=True)

    # print(success, pert_choice_groups)
    if not success:
        return False, None, None

    if choices[0].upper() == 'D':  # using defaults
        lf_map = (poles_pert_def[0], zeros_pert_def[0])  # beware, put poles then zeros in this map tuple
    else:
        lf_map = (pert_choice_groups[2], pert_choice_groups[1])

    # NOW HIGH FREQ
    zero_pert_choices = []
    pole_pert_choices = []
    for ndx, val in enumerate(paz_fit_hf.zeros()):
        if ndx in zeros_pert_def[1]:
            zero_pert_choices.append(str(val) + ' <==')
        else:
            zero_pert_choices.append(str(val))
    for ndx, val in enumerate(paz_fit_hf.poles()):
        if ndx in poles_pert_def[1]:
            pole_pert_choices.append(str(val) + ' <==')
        else:
            pole_pert_choices.append(str(val))

    pert_choices = [defchoice, zero_pert_choices, pole_pert_choices]
    success, choices, pert_choice_groups = pick2(pert_choices,
                                                 'Select HIGH FREQ zeros & poles to perturb',
                                                 prompt=prompt,
                                                 group_titles=grp_titles,
                                                 multiple_choice=True,
                                                 implicit_quit_q=True, menu_on_error=True)
    # print(success, pert_choice_groups)
    if not success:
        return False, None, None

    if choices[0].upper() == 'D':  # using defaults
        hf_map = (poles_pert_def[1], zeros_pert_def[1])  # beware, put poles then zeros in this map tuple
    else:
        hf_map = (pert_choice_groups[2], pert_choice_groups[1])

    return success, lf_map, hf_map  # each in (poles, zeros) order
