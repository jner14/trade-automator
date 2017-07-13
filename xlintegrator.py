import os
import random

import sys
import xlwings as xw
import pandas as pd
from pandas.tseries.offsets import BDay
pd.set_option('expand_frame_repr', False)
from datetime import datetime, time, date, timedelta
import string
from time import sleep

WORKBOOK_FILENAME = 'trade-dashboard.xlsm'
DEBUG = True

# Connect to the excel workbook
# Make sure trade-dashboard.xlsm is already open
try:
    wb = xw.books[WORKBOOK_FILENAME]
    print("[OK] successfully connected to the excel workbook")
except KeyError as e:
    print("[ERROR] Open %s before running this program!" % WORKBOOK_FILENAME)
    sys.exit()

# Connect to each of the sheets
reporting_sht = wb.sheets('Reporting')
existing_sht = wb.sheets('Existing')
monitoring_sht = wb.sheets('Monitoring')
data_sht = wb.sheets('Data')
config_sht = wb.sheets('Config')
orders_sht = wb.sheets('Orders')
forex_sht = wb.sheets('Forex')
tranche_sht = wb.sheets('Tranche Size')


# Grab conversion rate, exchange code, and symbol tables
CONV_RATE = forex_sht.range('B2').options(pd.DataFrame, expand='table').value
EXCH_CODE = forex_sht.range('F2').options(pd.DataFrame, expand='table').value
SYMBOLS = pd.read_excel('Shared Files\\MasterFileAT.xls', 'Link to Excel', index_col=0).dropna()
CURRENCIES = {comp: EXCH_CODE.loc[SYMBOLS.loc[comp, 'IG Tickers'].split('.')[-1], 'Currency'] for comp in SYMBOLS.index}
# TODO: add tranche size sheet and load it in the line below
TRANCHE_SZ = tranche_sht.range('B2').options(pd.DataFrame, expand='table').value.dropna()


# Create field label variables for the reporting sheet using a class to utilize dot notation
class rep_lbls:
    ALL_LBLS = "News Type	Re-rater, De-rater and Conviction	Trade Triggers	Buy/Sell	Limit % From Prev Close	Stretch Limit % From Prev Close	Target % From Prev Close	Stop Loss % From Prev Close	EOD Exit	Trade Amount (KUSD)	Reporting Date	Reporting Time	Short Term Price Strength	Long Term Price Strength	Entry Requirements	Exit Requirements".split('\t')
    NEWS, CONVICTION, TRIGGERS, BUY_SELL, LIMIT_PCT, STRETCH_LIMIT, TARGET_PCT, STOP_LOSS, EOD_EXIT, TRADE_AMT, REPORT_DATE, REPORT_TIME, SHORT_STRENGTH, LONG_STRENGTH, ENTRY_REQ, EXIT_REQ = ALL_LBLS
    FLD_IDS = dict(zip(ALL_LBLS, [x + '2' for x in string.uppercase[2: 2 + len(ALL_LBLS)]]))

    def __init__(self):
        pass


# Create field label variables for the existing sheet using a class to utilize dot notation
class net_lbls:
    ALL_LBLS = "eSignal Symbol	Symbol	Amount	Currency	AverageOpenPrice	Exchange Rate	KUSD	Re-rater, De-rater and Conviction	Reporting Date".split('\t')
    ESIGNAL_SYMBOL, SAXO_SYMBOL, AMOUNT, CURRENCY, AVE_PRICE, EXCH_RATE, TRADE_AMT, CONVICTION, REPORT_DATE = ALL_LBLS
    VALID_LBLS = [ESIGNAL_SYMBOL, CONVICTION, REPORT_DATE]
    FLD_IDS = dict(zip(ALL_LBLS, [x + '2' for x in string.uppercase[1: 1 + len(ALL_LBLS)]]))

    def __init__(self):
        pass


class Config:
    AUTO_SORT = None
    AUTO_REPORT_DATE = None
    MARKET_OPEN = None
    MARKET_CLOSE = None
    L2_ACCT = None
    L2_ENABLED = None
    SAXO_ACCT = None
    SAXO_CLIENT_KEY = None
    SAXO_ACCT_KEY = None
    SAXO_ENABLED = None
    TRANCHE_GAP = None
    TARGET_ORDER_TYPE = None

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
                Config.L2_ENABLED = config_sht.range('B8').value
                Config.SAXO_ACCT = config_sht.range('B9').value
                Config.SAXO_CLIENT_KEY = config_sht.range('B10').value
                Config.SAXO_ACCT_KEY = config_sht.range('B11').value
                Config.SAXO_ENABLED = config_sht.range('B12').value
                Config.TRANCHE_GAP = config_sht.range('B13').value
                Config.TARGET_ORDER_TYPE = config_sht.range('B14').value
                break
            except Exception as e:
                exception_msg(e, 'config')

        # Check values for potential problems
        assert (Config.TARGET_ORDER_TYPE == 'Limit' or Config.TARGET_ORDER_TYPE == 'Market'), \
            'Check "Target % Order Type" on the Config sheet'


def exception_msg(error, sheet):
    if 'Call was rejected by callee.' in error:
        print("\nFailed to access Config cells.  Pausing momentarily in case you're making changes.")
    elif DEBUG:
        print("[DEBUG][%s] %s" % (sheet, error))
    sleep(2)


def float_to_time(value):
    hour = int(value*24)
    minute = int((value*24) % 1 * 60 + .5)
    return time(hour=hour, minute=minute)


def get_reporting():
    while True:
        try:
            end = rep_lbls.FLD_IDS[rep_lbls.ALL_LBLS[-1]]
            df = reporting_sht.range('B2:%s53' % end[:-1]).options(pd.DataFrame).value.drop("").drop(None)
            break
        except Exception as e:
            exception_msg(e, 'reporting')

    if df[rep_lbls.REPORT_DATE].dtype == '<M8[ns]':
        df[rep_lbls.REPORT_DATE] = df[rep_lbls.REPORT_DATE].apply(lambda x: x.date())
    return df.fillna("")


def get_prev_close():
    prev_close = None
    while True:
        try:
            # TODO: consider running set_reporting_prev_close before, waiting to populate, then running the values
            prev_close = data_sht.range('Y2:AD2').options(pd.DataFrame, expand='vertical').value.fillna("").drop("")
        except Exception as e:
                exception_msg(e, 'data')
        # Return values if data pull was successful
        if prev_close is not None and (prev_close['Last'] == "").sum() == 0 and (prev_close['Volume'] == "").sum() == 0:
            return prev_close
        else:
            # Notify of data issue
            print("[ERROR] Latest data pull came back with empty values. " +
                  "Ensure Qlink is running and the data sheet is updating all cells.")
            sleep(2)
            # sys.exit()


def get_reporting_prev_close():
    while True:
        try:
            # TODO: consider running set_reporting_prev_close before, waiting to populate, then running the values
            return data_sht.range('Q2:X2').options(pd.DataFrame, expand='vertical').value.fillna("")
        except Exception as e:
                exception_msg(e, 'data')


def set_reporting_prev_close():
    reporting, existing, monitoring = get_reporting(), get_net_existing(), get_monitoring()
    reporting['Group'] = 'Reporting'
    existing['Group'] = 'Existing'
    monitoring['Group'] = 'Monitoring'
    lbls = ['Group', 'Reporting Date']
    all_groups = pd.concat([reporting[lbls], existing[lbls], monitoring[lbls]])
    all_groups = all_groups[~all_groups.index.duplicated()]
    empty_mask = ((all_groups[rep_lbls.REPORT_DATE].isnull()) |
                  (all_groups[rep_lbls.REPORT_DATE] == pd.NaT) |
                  all_groups[rep_lbls.REPORT_DATE].str.contains(''))
    # all_groups = all_groups[~empty_mask]
    all_groups.loc[empty_mask, rep_lbls.REPORT_DATE] = datetime.now().date()
    # Use the last weekday as prev close
    all_groups['Prev Close Date'] = all_groups[rep_lbls.REPORT_DATE] - BDay(1)
    if None in all_groups.index:
        all_groups.drop(None, inplace=True)

    while True:
        try:
            data_sht.range('Q3:S153').options(transpose=True).value = ""
            data_sht.range('Q2:S2').expand('vertical').value = all_groups[['Group', 'Prev Close Date']]
            break
        except Exception as e:
                exception_msg(e, 'data')


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
                    if field in rep_lbls.FLD_IDS.keys():
                        reporting_sht.range(rep_lbls.FLD_IDS[field]).options(index=False).value = df[field]
            break
        except Exception as e:
                exception_msg(e, 'reporting')


def get_net_existing(exclude_squared=True):
    while True:
        try:
            df = existing_sht.range('A2:J2').options(pd.DataFrame, expand='vertical').value
            break
        except Exception as e:
                exception_msg(e, 'existing-net')

    # Drop net positions that are square or drop empty rows and then fill na with ''
    if exclude_squared:
        df = df[df[net_lbls.TRADE_AMT] != 0]
    if '' in df.index:
        df.drop('', inplace=True)
    df = df.fillna('')

    # Get esignal symbols and set as index
    df[net_lbls.ESIGNAL_SYMBOL] = df[net_lbls.SAXO_SYMBOL].apply(lambda x:  SYMBOLS.loc[(SYMBOLS['Saxo Tickers'] == x), 'eSignal Tickers'].squeeze())
    df = df.set_index(net_lbls.ESIGNAL_SYMBOL)
    return df


def set_net_existing(df, fields=['all']):
    assert isinstance(fields, (list, tuple)), "'fields' parameter must by a list of field names"
    while True:
        try:
            if 'all' in fields:
                df[net_lbls.ESIGNAL_SYMBOL] = df.index
                # existing_sht.range(net_lbls.FLD_IDS[net_lbls.ESIGNAL_SYMBOL]).options(index=False).value = pd.DataFrame(df.index, columns=[net_lbls.ESIGNAL_SYMBOL])
                for field in net_lbls.VALID_LBLS:
                    existing_sht.range(net_lbls.FLD_IDS[field]).options(index=False).value = df[field]
            else:
                for field in fields:
                    if field in net_lbls.VALID_LBLS and field in net_lbls.FLD_IDS.keys():
                        existing_sht.range(net_lbls.FLD_IDS[field]).options(index=False).value = df[field]
                    else:
                        print('[WARNING] field=%s is not in net_lbls.' % field)
            break
        except Exception as e:
                exception_msg(e, 'reporting')


def get_all_existing():
    while True:
        try:
            df = existing_sht.range('Q2:Y103').options(pd.DataFrame).value
            break
        except Exception as e:
                exception_msg(e, 'existing-all')

    # Drop empty rows and fill NANs with ''
    if '' in df.index:
        df.drop("", inplace=True)
    if None in df.index:
        df.drop(None, inplace=True)
    df = df.fillna("")

    # time_lbl = "ExecutionTimeOpen"
    # if df[time_lbl].dtype == '<M8[ns]':
    #     df[time_lbl] = df[time_lbl].apply(lambda x: x.date())
    return df


def get_monitoring():
    while True:
        try:
            return monitoring_sht.range('B2').options(pd.DataFrame, expand='table').value.fillna("")
        except Exception as e:
                exception_msg(e, 'monitoring')


def get_latest():
    while True:
        try:
            latest_reporting = data_sht.range('B2:E2').options(pd.DataFrame, expand='vertical').value
            latest_existing = data_sht.range('G2:J2').options(pd.DataFrame, expand='vertical').value
            latest_monitoring = data_sht.range('L2:O2').options(pd.DataFrame, expand='vertical').value
            break
        except Exception as e:
                exception_msg(e, 'data')

    latest_reporting['Group'] = 'Reporting'
    latest_existing['Group'] = 'Existing'
    latest_monitoring['Group'] = 'Monitoring'

    if Config.AUTO_SORT:
        latest_reporting.sort_index(inplace=True)
        latest_existing.sort_index(inplace=True)
        latest_monitoring.sort_index(inplace=True)

    latest = pd.concat([latest_reporting, latest_existing, latest_monitoring])
    if '' in latest.index:
        latest.drop("", inplace=True)

    # Check if data pulled has empty values
    if (latest['Last'] == "").sum() > 0 or (latest['Volume'] == "").sum() > 0 or (latest['Last Time'] == "").sum() > 0:
        # Notify of data issue
        print("[ERROR] Latest data pull came back with empty values. " +
              "Ensure Qlink is running and the data sheet is updating all cells.")
        sleep(2)
        # sys.exit()

    latest['Last Time'] = latest['Last Time'].apply(lambda x: xl_ts_2_datetime(x))
    return latest.fillna("")


def get_reporting_day():
    while True:
        try:
            return reporting_sht.range('D1').value.date()
        except Exception as e:
                exception_msg(e, 'reporting')


def send_order(company, order_msg, alt_order_msg):

    # Send order
    while True:
        try:
            # Get the order count
            sent_orders = get_sent_orders()
            new_loc = len(sent_orders) + 3
            time_now = datetime.now().replace(microsecond=0)
            # TODO: add take profit and any other missing fields below

            # Update order sheet, sending the order to Saxo
            orders_sht.range('T%s' % new_loc).value = [company, alt_order_msg, order_msg[1:], time_now]

            # Wait for order response
            while True:
                order_res = orders_sht.range('U%s' % new_loc).value
                if order_res == alt_order_msg:
                    print('[INFO] send_order() - waiting for order response from saxo')
                    sleep(1)
                else:
                    break
            break
        except Exception as e:
            exception_msg(e, 'orders')

    # Update dashboard
    while True:
        try:
            # Remove order info from reporting tab
            reporting = get_reporting()
            esig_symbol = SYMBOLS.loc[company, "eSignal Tickers"]
            reporting.loc[esig_symbol, rep_lbls.BUY_SELL] = "sent"
            set_reporting(reporting)
            break
        except Exception as e:
            exception_msg(e, 'reporting')
    return order_res


def xl_ts_2_datetime(xldate):
    assert type(xldate) == float, '[ERROR][xl_ts_2_datetime] xldate=%s is not a valid float value' % xldate
    temp = datetime(1899, 12, 30)
    delta = timedelta(days=xldate)
    return temp + delta


def get_working_orders():
    work_orders = orders_sht.range('B2:Q50').options(pd.DataFrame, ).value
    if '' in work_orders.index:
        work_orders.drop("", inplace=True)
    if None in work_orders.index:
        work_orders.drop(None, inplace=True)
    work_orders = work_orders.fillna("")
    work_orders['OrderTime'] = work_orders['OrderTime'].apply(lambda x: xl_ts_2_datetime(x))
    return work_orders


def get_sent_orders():
    return orders_sht.range('T2').options(pd.DataFrame, expand='vertical').value


def L2_auto_trade(company, side, price, trade_amt, order_type, good_til, expiry="", stop=""):
    if expiry != "":
        expiry = '"%s"' % expiry

    # Grab currency using the ig symbol
    ig_symbol = SYMBOLS.loc[company, 'IG Tickers']
    currency = EXCH_CODE.loc[ig_symbol.split('.')[-1], 'Currency']

    if currency == 'USD':
        conv_rate = 1
    else:
        conv_rate = CONV_RATE.loc[currency, 'Conversion Rate']

    # Calculate number of shares using the trade amount, conversion rate, and limit price
    trade_size = int((trade_amt * 1000.0 * conv_rate) / price)

    # Create L2Send text
    message = '=L2Send("{}","{}",{},{},{},{},{},{},{})'.format(Config.L2_ACCT,
                                                               ig_symbol,
                                                               side,
                                                               price,
                                                               trade_size,
                                                               order_type,
                                                               good_til,
                                                               expiry,
                                                               stop)
    if not Config.L2_ENABLED:
        msg = "SIM#%s" % random.randint(100000, 999999)
    else:
        msg = message
    while True:
        try:
            # Get the order count
            curr_orders = orders_sht.range('C2').options(pd.DataFrame, expand='vertical').value
            new_loc = len(curr_orders) + 3
            time_now = datetime.now().replace(microsecond=0)

            orders_sht.range('B%s' % new_loc).value = [time_now,
                                                       company,
                                                       msg,
                                                       "",
                                                       "",
                                                       "",
                                                       side,
                                                       price,
                                                       trade_amt,
                                                       trade_size,
                                                       order_type,
                                                       good_til,
                                                       expiry,
                                                       stop,
                                                       message[1:]]
            if not Config.L2_ENABLED:
                print("The following SIMULATED order has been sent: %s" % message)
            else:
                print("The following order has been sent: %s" % message)

            # Remove order info from reporting tab
            reporting = get_reporting()
            esig_symbol = SYMBOLS.loc[company, "eSignal Tickers"]
            reporting.loc[esig_symbol, rep_lbls.BUY_SELL] = "sent"
            set_reporting(reporting)
            return
        except Exception as e:
            exception_msg(e, 'orders')


def L2_get_status():
    while True:
        try:
            # Ger order IDs
            orders = orders_sht.range('B2:P2').options(pd.DataFrame, expand='vertical').value.fillna("")
            break
        except Exception as e:
            exception_msg(e, 'orders')

    # Update status, filled amount, and average price in array
    for k, v in orders['Order ID'].iteritems():
        if not Config.L2_ENABLED:
            orders.loc[k, 'Status'] = "Filled"
            orders.loc[k, 'Filled Amount'] = orders.loc[k, 'Trade Size']
            orders.loc[k, 'Average Price'] = orders.loc[k, 'Order Price']
        elif orders.loc[k, 'Status'] == "":
            orders.loc[k, 'Status'] = "=L2OrderStatus(%s)" % v
            orders.loc[k, 'Filled Amount'] = "=L2OrderFillSize(%s)" % v
            orders.loc[k, 'Average Price'] = "=L2OrderAvgPrice(%s)" % v
        elif orders.loc[k, 'Status'] == "FILLED":
            orders.loc[k, 'Filled Amount'] = orders.loc[k, 'Filled Amount'].split(":")[-1]
            orders.loc[k, 'Average Price'] = orders.loc[k, 'Average Price'].split(":")[-1]
        else:
            orders.loc[k, 'Filled Amount'] = ""
            orders.loc[k, 'Average Price'] = ""

    while True:
        try:
            # Update orders table with updated array
            orders_sht.range('B2').value = orders
            return
        except Exception as e:
            exception_msg(e, 'orders')


# def saxo_create_order(company, asset_type, trade_amt, side, duration="DayOrder", order_type="Market", price=0.0, take_profit=None, stop=None, stop_type="StopIfTraded"):
#
#     # Grab currency using the ig symbol
#     ig_symbol = SYMBOLS.loc[company, 'IG Tickers']
#     currency = EXCH_CODE.loc[ig_symbol.split('.')[-1], 'Currency']
#
#     if currency == 'USD':
#         conv_rate = 1
#     else:
#         conv_rate = CONV_RATE.loc[currency, 'Conversion Rate']
#
#     # Calculate number of shares using the trade amount, conversion rate, and limit price
#     if price != 0.0:
#         trade_size = int((trade_amt * 1000.0 * conv_rate) / price)
#     else:
#         print(['[DEBUG] SAXO_CREATE_ORDER - must pass the limit or last price'])
#         sys.exit()
#
#     # Get side string
#     if side == 1 or side == '1':
#         side_str = 'Buy'
#     elif side == 2 or side == '2':
#         side_str = 'Sell'
#     else:
#         print('[WARNING] Value passed for order side is not valid, ORDER NOT SENT!')
#         return
#
#     # Create Saxo order function text
#     message = '=OpenApiPlaceOrder("{}","{}","{}",{},"{}","{}","{}",{}'.format(Config.SAXO_ACCT_KEY,
#                                                                               SYMBOLS.loc[company, 'Saxo Tickers'],
#                                                                               asset_type,
#                                                                               trade_size,
#                                                                               side_str,
#                                                                               duration,
#                                                                               order_type,
#                                                                               round(price, 2))
#     if take_profit is not None:
#         message += ',%s' % round(take_profit, 2)
#     if stop is not None:
#         message += ',{},"{}"'.format(round(stop, 2), stop_type)
#     message += ')'
#
#     # Alter the message to indicate it is simulated if so
#     if not Config.SAXO_ENABLED:
#         msg = "SIM#%s" % random.randint(100000, 999999)
#     else:
#         msg = message
#
#     # Update dashboard and send order
#     while True:
#         try:
#             # Get the order count
#             curr_orders = orders_sht.range('T2').options(pd.DataFrame, expand='vertical').value
#             new_loc = len(curr_orders) + 3
#             time_now = datetime.now().replace(microsecond=0)
#             # TODO: add take profit and any other missing fields below
#
#             # Update order sheet, sending order too
#             orders_sht.range('T%s' % new_loc).value = [company,
#                                                           msg,
#                                                           message[1:],
#                                                           time_now]
#             if not Config.SAXO_ENABLED:
#                 print("The following SIMULATED order has been sent: %s" % message)
#             else:
#                 print("The following order has been sent: %s" % message)
#
#             # Remove order info from reporting tab
#             reporting = get_reporting()
#             esig_symbol = SYMBOLS.loc[company, "eSignal Tickers"]
#             reporting.loc[esig_symbol, rep_lbls.BUY_SELL] = "sent"
#             set_reporting(reporting)
#             return
#         except Exception as e:
#             exception_msg(e, 'orders')


# def check_for_orders():
#     prev_close = get_prev_close()
#     future_orders = []
#
#     # TODO: switch prev_close_rep to prev_close
#     # If certain conditions are met then make an order
#     for k, v in get_reporting().iterrows():
#
#         # If values have been entered for, Buy/Sell, % Limit, Trade Amount, and one of the exit columns (target%, stop, EOD) then create an order
#         if (v[rep_lbls.LIMIT_PCT] != "" and v[rep_lbls.TRADE_AMT] != "" and
#                 (v[rep_lbls.BUY_SELL] == 1 or v[rep_lbls.BUY_SELL] == 2) and
#                 (v[rep_lbls.TARGET_PCT] != "" or v[rep_lbls.STOP_LOSS] != "" or v[rep_lbls.EOD_EXIT] != "")):
#
#             company = SYMBOLS.loc[(SYMBOLS['eSignal Tickers'] == k)].index[0]
#             side = v[rep_lbls.BUY_SELL]
#
#             # Calculate the limit price based off of the close previous to reporting day
#             limit_price = (1 + v[rep_lbls.LIMIT_PCT]) * prev_close.loc[k, 'Last']
#
#             # Calculate the stop loss
#             stop_str = v[rep_lbls.STOP_LOSS]
#             if stop_str != '' and stop_str != 0 and not None:
#                 multiplier = 1.0 if v[rep_lbls.BUY_SELL] == 2 else -1.0
#                 try:
#                     stop_loss = limit_price * (1 + multiplier * abs(float(stop_str)))
#                 except:
#                     stop_loss = None
#                     print('[ERROR] "%s" is not a valid stop loss value' % stop_str)
#             else:
#                 stop_loss = None
#
#             # Define the target % future orders
#             target_str = v[rep_lbls.TARGET_PCT]
#             if target_str != '' and target_str != 0 and not None:
#                 tranche_cnt = (v[rep_lbls.TRADE_AMT] / TRANCHE_SZ.loc[k])
#                 start_range = -tranche_cnt + int(.5 * tranche_cnt + .5)
#                 end_range = tranche_cnt - int(.5 * tranche_cnt)
#                 multiplier = 1.0 if v[rep_lbls.BUY_SELL] == 1 else -1.0
#                 # Get target_side
#                 if side == 1 or side == '1':
#                     target_side = 2
#                 elif side == 2 or side == '2':
#                     target_side = 1
#                 else:
#                     target_side = None
#                 # Get target float value
#                 try:
#                     target_flt = abs(float(target_str))
#                     target_price = (1. + target_flt * multiplier) * prev_close.loc[k, 'Last']
#                 except:
#                     target_price = None
#                     print('[ERROR] "%s" is not a valid target percent value' % target_str)
#                 # Create tranche orders to return as future orders
#                 if target_price is not None:
#                     for i in range(start_range, end_range):
#                         future_orders.append({
#                             'company': company,
#                             'trade_amt': TRANCHE_SZ.loc[k],
#                             'side': target_side,
#                             'price': (1 + i * Config.TRANCHE_GAP) * target_price,
#                             'valid_from': v[rep_lbls.REPORT_DATE],
#                             'order_type': 'target-limit'})
#
#             # Send order (company, asset_type, trade_amt, side, duration="DayOrder", order_type="Market", price=0.0, take_profit=None, stop=None, stop_type="StopIfTraded")
#             saxo_create_order(company=company,
#                               asset_type='CfdOnStock',
#                               trade_amt=v[rep_lbls.TRADE_AMT],
#                               side=side,
#                               duration='DayOrder',
#                               order_type='Limit',
#                               price=limit_price,
#                               stop=stop_loss,
#                               )
#
#     return future_orders


if __name__ == '__main__':

    # latest_prices = get_latest()
    # reporting_day = get_reporting_day()
    # reporting_table = get_reporting()
    # reporting_table[FieldLabels.REPORT_DATE].iloc[0] = datetime.now().date()
    # reporting_table.sort_index(inplace=True)
    # set_reporting(reporting_table, fields=[])
    # set_reporting(reporting_table, fields=[FieldLabels.REPORT_DATE])
    # prev_close = get_reporting_prev_close()
    pass

print("[OK] xlintegrator imported")