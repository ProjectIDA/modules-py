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
from pandas.core.frame import DataFrame

import ida.db.datascope.query


def find_sensor_file(df, station, loca, comp, date_8601_str):

    if isinstance(df, DataFrame):
        dfile_list = ida.db.datascope.query.find_sensor_file(df, station, loca, comp, date_8601_str)
    else:
        dfile_list = None

    return dfile_list
