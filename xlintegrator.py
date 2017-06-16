import os

import sys
import xlwings as xw
import pandas as pd
from datetime import datetime, time, date, timedelta
import string
from time import sleep

WORKBOOK_FILENAME = 'trade-dashboard.xlsm'
DEBUG = True

# Make sure trade-dashboard.xlsm is already open
try:
    with open(WORKBOOK_FILENAME, "a") as workbook:
        raise AssertionError
except IOError as e:
    print("[OK] %s appears to be running" % WORKBOOK_FILENAME)
except AssertionError as e:
    print("[ERROR] Open %s before running this program!" % WORKBOOK_FILENAME)
    sys.exit()

# Connect to the excel workbook, open if not already open
wb = xw.Book(WORKBOOK_FILENAME)
print("[OK] successfully connected to the excel workbook")

# Connect to each of the sheets
reporting_sht = wb.sheets('Reporting')
existing_sht = wb.sheets('Existing')
monitoring_sht = wb.sheets('Monitoring')
data_sht = wb.sheets('Data')
config_sht = wb.sheets('Config')


# Create field label variables using a class to utilize dot notation
class FieldLabels:
    ALL_LABELS = "News Type	Re-rater, De-rater and Conviction	Trade Triggers	Buy/Sell	% Limit	Target % Price Change	Trade Amount	Reporting Date	Reporting Time	Short Term Price Strength	Long Term Price Strength	Entry Requirements	Exit Requirements".split('\t')
    NEWS, CONVICTION, TRIGGERS, BUY_SELL, LIMIT, TARGET, TRADE_SZ, REPORT_DATE, REPORT_TIME, SHORT_STRENGTH, LONG_STRENGTH, ENTRY_REQ, EXIT_REQ = ALL_LABELS
    FIELD_IDS = dict(zip(ALL_LABELS, [x + '2' for x in string.uppercase[2: 2 + len(ALL_LABELS)]]))

    def __init__(self):
        pass


class Config:
    AUTO_SORT = None
    AUTO_REPORT_DATE = None
    MARKET_OPEN = None
    MARKET_CLOSE = None
    L2_ACCT = None

    def __init__(self):
        pass

    @staticmethod
    def get_config_options():
        while True:
            try:
                Config.AUTO_SORT = config_sht.range('B3').value
                Config.AUTO_REPORT_DATE = config_sht.range('B4').value
                Config.MARKET_OPEN = float_to_time(config_sht.range('B5').value)
                Config.MARKET_CLOSE = float_to_time(config_sht.range('B6').value)
                Config.L2_ACCT = config_sht.range('B7').value
                break
            except Exception as e:
                print("\nFailed to access Config cells.  Pausing until you've finished making changes.")
                if DEBUG:
                    print("[DEBUG][config] %s" % e)
                sleep(2)


def float_to_time(value):
    hour = int(value*24)
    minute = int((value*24) % 1 * 60 + .5)
    return time(hour=hour, minute=minute)


def get_reporting():
    while True:
        try:
            df = reporting_sht.range('B2').options(pd.DataFrame, expand='table').value
            if df[FieldLabels.REPORT_DATE].dtype == '<M8[ns]':
                df[FieldLabels.REPORT_DATE] = df[FieldLabels.REPORT_DATE].apply(lambda x: x.date())
            return df.fillna("")
        except Exception as e:
            print("\nFailed to access Reporting cells.  Pausing until you've finished making changes.")
            if DEBUG:
                print("[DEBUG][reporting] %s" % e)
            sleep(2)


def get_reporting_prev_close():
    while True:
        try:
            # TODO: consider running set_reporting_prev_close before, waiting to populate, then running the values
            return data_sht.range('Q2').options(pd.DataFrame, expand='table').value.fillna("")
        except Exception as e:
            print("\nFailed to access Data cells.  Pausing until you've finished making changes.")
            if DEBUG:
                print("[DEBUG][data] %s" % e)
            sleep(2)


def set_reporting_prev_close(reporting, existing, monitoring):
    while True:
        try:
            reporting['Group'] = 'Reporting'
            existing['Group'] = 'Existing'
            monitoring['Group'] = 'Monitoring'
            lbls = ['Group', 'Reporting Date']
            all_groups = pd.concat([reporting[lbls], existing[lbls], monitoring[lbls]])
            empty_mask = ((all_groups[FieldLabels.REPORT_DATE].isnull()) |
                          (all_groups[FieldLabels.REPORT_DATE] == pd.NaT) |
                          all_groups[FieldLabels.REPORT_DATE].str.contains(''))
            all_groups = all_groups[~empty_mask]
            all_groups['Prev Close Date'] = all_groups[FieldLabels.REPORT_DATE] - timedelta(days=1)
            data_sht.range('Q3:S153').options(transpose=True).value = ""
            data_sht.range('Q2').value = all_groups[['Group', 'Prev Close Date']]
            break
        except Exception as e:
            print("\nFailed to access Data cells.  Pausing until you've finished making changes.")
            if DEBUG:
                print("[DEBUG][data] %s" % e)
            sleep(2)


def set_reporting(df, fields=['all']):
    assert isinstance(fields, (list, tuple)), "'fields' parameter must by a list of field names"
    while True:
        try:
            # if FieldLabels.REPORT_DATE in fields or 'all' in fields:
            #     df[FieldLabels.REPORT_DATE] = df[FieldLabels.REPORT_DATE].apply(lambda x: x.date() if type(x) == pd._libs.tslib.Timestamp else x)
            if 'all' in fields:
                if Config.AUTO_SORT:
                    df.sort_index(inplace=True)
                reporting_sht.range('B2').value = df
            else:
                for field in fields:
                    if field in FieldLabels.FIELD_IDS.keys():
                        reporting_sht.range(FieldLabels.FIELD_IDS[field]).options(index=False).value = df[field]
            break
        except Exception as e:
            print("\nFailed to access Reporting cells.  Pausing until you've finished making changes.")
            if DEBUG:
                print("[DEBUG][reporting] %s" % e)
            sleep(2)


def get_existing():
    while True:
        try:
            df = existing_sht.range('B2').options(pd.DataFrame, expand='table').value
            if df[FieldLabels.REPORT_DATE].dtype == '<M8[ns]':
                df[FieldLabels.REPORT_DATE] = df[FieldLabels.REPORT_DATE].apply(lambda x: x.date())
            return df.fillna("")
        except Exception as e:
            print("\nFailed to access Existing cells.  Pausing until you've finished making changes.")
            if DEBUG:
                print("[DEBUG][existing] %s" % e)
            sleep(2)


def get_monitoring():
    while True:
        try:
            return monitoring_sht.range('B2').options(pd.DataFrame, expand='table').value.fillna("")
        except Exception as e:
            print("\nFailed to access Monitoring cells.  Pausing until you've finished making changes.")
            if DEBUG:
                print("[DEBUG][monitoring] %s" % e)
            sleep(2)


def get_latest():
    while True:
        try:
            latest_reporting = data_sht.range('B2:E2').options(pd.DataFrame, expand='vertical').value
            latest_reporting['Group'] = 'Reporting'
            latest_existing = data_sht.range('G2:J2').options(pd.DataFrame, expand='vertical').value
            latest_existing['Group'] = 'Existing'
            latest_monitoring = data_sht.range('L2:O2').options(pd.DataFrame, expand='vertical').value
            latest_monitoring['Group'] = 'Monitoring'

            if Config.AUTO_SORT:
                latest_reporting.sort_index(inplace=True)
                latest_existing.sort_index(inplace=True)
                latest_monitoring.sort_index(inplace=True)

            latest = pd.concat([latest_reporting, latest_existing, latest_monitoring])
            latest.drop("", inplace=True)
            latest['Last Time'] = latest['Last Time'].apply(lambda x: xl_ts_2_datetime(x))
            return latest.fillna("")
        except Exception as e:
            print("\nFailed to access Data cells.  Pausing until you've finished making changes.")
            if DEBUG:
                print("[DEBUG][data] %s" % e)
            sleep(2)


def get_reporting_day():
    while True:
        try:
            return reporting_sht.range('D1').value.date()
        except Exception as e:
            print("\nFailed to access Reporting cells.  Pausing until you've finished making changes.")
            if DEBUG:
                print("[DEBUG][reporting] %s" % e)
            sleep(2)


def xl_ts_2_datetime(xldate):
    temp = datetime(1899, 12, 30)
    delta = timedelta(days=xldate)
    return temp + delta


def L2_auto_trade(symbol, side, price, size, order_type, good_til, expiry="", stop=""):
    if expiry != "":

        expiry = '"%s"' % expiry
    message = '=L2Send("{}","{}",{},{},{},{},{},{},{})'.format(Config.L2_ACCT,
                                                               symbol,
                                                               side,
                                                               price,
                                                               size,
                                                               order_type,
                                                               good_til,
                                                               expiry,
                                                               stop)

if __name__ == '__main__':

    latest_prices = get_latest()
    reporting_day = get_reporting_day()
    reporting_table = get_reporting()
    # reporting_table[FieldLabels.REPORT_DATE].iloc[0] = datetime.now().date()
    # reporting_table.sort_index(inplace=True)
    # set_reporting(reporting_table, fields=[])
    # set_reporting(reporting_table, fields=[FieldLabels.REPORT_DATE])
    # prev_close = get_reporting_prev_close()

print("[OK] xlintegrator imported")
