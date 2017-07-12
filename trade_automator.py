import pandas as pd
pd.set_option('expand_frame_repr', False)
# from py_qlink import QLinkConn
from time import sleep
from datetime import datetime, time, timedelta
from xlintegrator import get_reporting, get_latest, rep_lbls, net_lbls, Config, set_reporting, L2_get_status, \
    set_reporting_prev_close, get_net_existing, get_monitoring, L2_auto_trade, get_reporting_day, get_reporting_prev_close, \
    get_prev_close, CONV_RATE, EXCH_CODE, SYMBOLS, TRANCHE_SZ, set_net_existing, \
    CURRENCIES
from algos import consolidation_breakout
from trade_utils import change_time
import re
import math
import sys
from PyQt5.QtWidgets import QApplication
from order_window import OrderWindow
from orders import *


BAR_LABELS = ['Open', 'High', 'Low', 'Close', 'Volume']
POLL_LABELS = ['Last', 'Volume']
TIME_FORMAT = "%I:%M:%S %p"
UPDATE_INTERVAL = 15  # seconds
IGNORE_MKT_HRS = True

period = 1
poll_data = {}
first_run = True
bars = {}
order_manager = OrderManager()
while True:
    # Get the time and print it to console
    time_now = datetime.now().time()
    first_second = time_now.second
    print("The time is %s" % time_now.strftime(TIME_FORMAT))

    # Update config options
    Config.get_config_options()

    # Run this only if the program was just started
    if first_run:

        # Get current positions
        existing = get_net_existing()

        # Get previous close for all companies
        prev_close = get_prev_close()

        # Get the latest

        # If its the first run then generate stop orders for current positions
        # TODO: test creating trailing-stop future orders for straight-forward trades
        # TODO: move tranche calculations to the saxo order function, even the number of stop orders to place needs to be calculated at the time the tranche order is executed making all this below, useless
        # for k, v in existing.iterrows():
        #     tranche_cnt = int(math.ceil(v[net_lbls.AMOUNT] * latest.loc[k, 'Last'] / TRANCHE_SZ.loc[k]))
        #     start_range = -tranche_cnt + int(.5 * tranche_cnt + .5)
        #     end_range = tranche_cnt - int(.5 * tranche_cnt)
        #     # Create tranche orders
        #     for i in range(start_range, end_range):
        #         company = SYMBOLS.loc[(SYMBOLS['eSignal Tickers'] == k)].index[0]
        #         side = 1 if v[net_lbls.AMOUNT] < 0 else 2
        #         stop_diff = .04 if v[net_lbls.CONVICTION].lower() == 's' else .01
        #         stop_price = (1. + .01 * multiplier) * prev_close.loc[k, 'Last']
        #         future_orders.append({
        #             'company': company,
        #             'trade_amt': TRANCHE_SZ.loc[k].squeeze(),
        #             'side': side,
        #             'price': (1 + i * Config.TRANCHE_GAP) * stop_price,
        #             'valid_from': datetime.now().date(),
        #             'order_type': 'trailing-stop-market'
        #         })

        # TODO: Remove yesterday's reporting today companies, moving to monitoring if none were traded
        if (Config.MARKET_OPEN < time_now < Config.MARKET_CLOSE) or IGNORE_MKT_HRS:
            pass

        # Set reporting date to today's date if it is currently None or NaT, i.e. empty
        reporting_table = get_reporting()
        if Config.AUTO_REPORT_DATE:
            report_day = datetime.now().date()
            reporting_table[rep_lbls.REPORT_DATE] = \
                reporting_table[rep_lbls.REPORT_DATE].apply(
                    lambda x: report_day if x is None or x is pd.NaT or x == '' else x)
            set_reporting(reporting_table, [rep_lbls.REPORT_DATE])

    # Run this only during the minute before market open
    # TODO: fix this for times when program is started after market hours have begun
    if time_now < change_time(Config.MARKET_OPEN, -1) or time_now > Config.MARKET_CLOSE:
        print("Market hours are configured as {} - {}".format(Config.MARKET_OPEN.strftime(TIME_FORMAT),
                                                              Config.MARKET_CLOSE.strftime(TIME_FORMAT)))
    #     prev_close = get_latest()
    #     print("Will proceed after market hours begin.")
    # elif change_time(Config.MARKET_OPEN, -1) < time_now < Config.MARKET_OPEN:
    #     prev_close = get_latest()
    #     print("Beginning in less than one minute.")
    # else:
    #     # comp_names = get_latest().index
    #     set_reporting_prev_close()
    #     prev_close_rep = get_reporting_prev_close()
    #     prev_close = get_prev_close()
    set_reporting_prev_close()

    # Waiting until market opens
    orders_sent = False
    while (time_now < Config.MARKET_OPEN or time_now > Config.MARKET_CLOSE) and not IGNORE_MKT_HRS:

        # Send orders to Saxo 3 seconds before the open
        if Config.MARKET_OPEN > time_now > change_time(Config.MARKET_OPEN, -1) and not orders_sent:
            seconds_before = 3.0
            time_left = 60.0 - seconds_before - time_now.second + time_now.microsecond / 1e6
            print("\nExecuting orders in %s seconds" % time_left)
            sleep(time_left)
            print("The time is %s" % datetime.now().strftime(TIME_FORMAT))
            print("Executing orders...")

            # Check for order before market opens
            order_manager.check_for_opening_orders()

            orders_sent = True
            print("The time is %s" % datetime.now().strftime(TIME_FORMAT))
            print("Finished...")

        if datetime.now().second == first_second:
            # Update config options
            Config.get_config_options()
            print('.')
        else:
            print('.'),
        # Wait a second and check time again
        sleep(1)
        time_now = datetime.now().time()
    print('')

    # Collect some data from excel and update empty reporting day fields
    # existing_table = get_net_positions()
    monitoring_table = get_monitoring()

    # Run only once
    # if first_run:
    #     # Update reporting day previous close table
    #     set_reporting_prev_close(reporting_table, existing_table, monitoring_table)
    #     first_run = False

    ### Calculate how much time to wait for next 15 second interval and then wait
    time_now = datetime.now().time()
    current_secs = time_now.second + time_now.microsecond / 1e6  # .replace(hour=0, minute=0)
    time_left = (int(current_secs / float(UPDATE_INTERVAL)) * UPDATE_INTERVAL + UPDATE_INTERVAL) - current_secs
    print("Waiting %s seconds" % time_left)
    sleep(time_left)

    prev_close_rep = get_reporting_prev_close()
    prev_close = get_prev_close()

    ### Grab latest price and volume
    #     POLL_LABELS = ['Last', 'Volume']
    assert prev_close is not None, "prev_close has not been gathered"
    latest = get_latest()
    # For every symbol see if the latest volume is different from yesterday's and if so begin collecting data
    for k, v in latest.iterrows():
        if k not in poll_data.keys():
            poll_data[k] = pd.DataFrame(columns=POLL_LABELS)
        if k in prev_close.index and v.Volume != prev_close.loc[k, 'Volume']:  # or True:
            poll_data[k].loc[v['Last Time']] = v[POLL_LABELS]
            if len(poll_data[k]) > 1:
                poll_data[k].ix[-1, 'Volume'] -= poll_data[k].ix[0:-1, 'Volume'].sum()

    ### At the close of a bar, create new bars and run algos
    BAR_SIZE = 1
    time_now = datetime.now().time()
    if (time_now.minute % BAR_SIZE == 0 and (5 > time_now.second or time_now.second > 55)):

        # Create 5 minute bars at the end of every bar
        assert len(poll_data) > 0, "poll_data has not been gathered"
        for k, v in poll_data.iteritems():
            if len(v) == 0:
                continue
            # Create empty DataFrames for any new symbols in poll_data
            # if k not in bars.keys():
            bars[k] = pd.DataFrame(columns=BAR_LABELS)
            # Resample poll_data into 5 minute bars
            try:
                resampled = v.resample('%dT' % BAR_SIZE)
            except:
                print("stop")
            bars[k]['Open'] = resampled['Last'].first()
            bars[k]['High'] = resampled['Last'].max()
            bars[k]['Low'] = resampled['Last'].min()
            bars[k]['Close'] = resampled['Last'].last()
            bars[k]['Volume'] = resampled['Volume'].sum().fillna(0)
            # Fill empty bars with previous close
            nanMsk = bars[k]['Open'].isnull()
            bars[k]['Close'] = bars[k]['Close'].ffill()
            bars[k].loc[nanMsk, 'Open'] = bars[k].loc[nanMsk, 'Close']
            bars[k].loc[nanMsk, 'High'] = bars[k].loc[nanMsk, 'Close']
            bars[k].loc[nanMsk, 'Low'] = bars[k].loc[nanMsk, 'Close']
            print("[DEBUG] symbol=%s, last_bar=%s" % (k, list(bars[k].iloc[-1])))


        # # Print time elapsed since starting marker
        # print('Time Elapsed: %s' % (datetime.now() - st))

        # Check for consolidation breakouts
        # TODO: got AssertionError: Can not find column header=Last. Required column headers: ['Open', 'High', 'Low', 'Last', 'Intraday_Time', 'Intraday_Date']
        # breakouts = {}
        # for k, v in bars.iteritems():
        #     breakouts[k] = []
        #     if len(v) >= 5:
        #         breakouts[k] = consolidation_breakout(v)

        # Get the reporting and existing sheets
        reporting_table = get_reporting()

                    # Check for price target met
        # pt_matches = reporting_table[rep_lbls.ENTRY_REQ].str.extract(r'price\(([\d.]+)\)', expand=True).dropna()
        # for k, v in pt_matches.iteritems():
        #     print(k, v)

        # Check for price move 1% or 2%
        for k, v in bars.iteritems():
            if k not in reporting_table.index: continue
            try:
                if .99 * prev_close.loc[k, 'Last'] > v.ix[-1, 'Close'] or v.ix[-1, 'Close'] > 1.01 * prev_close.loc[k, 'Last']:
                    if "1%Change" not in reporting_table.loc[k, rep_lbls.TRIGGERS]:
                        if reporting_table.loc[k, rep_lbls.TRIGGERS] != "":
                            reporting_table.loc[k, rep_lbls.TRIGGERS] += ",1%Change"
                        else:
                            reporting_table.loc[k, rep_lbls.TRIGGERS] = "1%Change"

                if .98 * prev_close.loc[k, 'Last'] > v.ix[-1, 'Close'] or v.ix[-1, 'Close']  > 1.02 * prev_close.loc[k, 'Last']:
                    if "2%Change" not in reporting_table.loc[k, rep_lbls.TRIGGERS]:
                        if reporting_table.loc[k, rep_lbls.TRIGGERS] != "":
                            reporting_table.loc[k, rep_lbls.TRIGGERS] += ",2%Change"
                        else:
                            reporting_table.loc[k, rep_lbls.TRIGGERS] = "2%Change"
            except Exception as e:
                print(e)

        # for k, v in reporting_table.iterrows():
        #     price_req = re.(v[rep_lbls.ENTRY_REQ])
        #     if "price(" in v[rep_lbls.ENTRY_REQ].lower():


        # # For any new consolidation breakouts update Reporting sheet
        # for k, v in reporting_table.iterrows():
        #     if len(breakouts[k]) > 0 and breakouts[k].iloc[-1] == True:
        #         if reporting_table.loc[k, rep_lbls.TRIGGERS] != "":
        #             reporting_table.loc[k, rep_lbls.TRIGGERS] += ",ConBreak"
        #         else:
        #             reporting_table.loc[k, rep_lbls.TRIGGERS] = "ConBreak"
        set_reporting(reporting_table)

        # TODO: remove this check_for_opening_orders call after testing
        order_manager.check_for_opening_orders()

    # Get existing net positions
    existing_table = get_net_existing(exclude_squared=False)

    # TODO: clear fields from previous day square positions
    # Check for changes to existing positions and update fields of new positions
    chg_existing = False
    for k, v in existing_table.iterrows():
        # Check conviction column
        if v[net_lbls.CONVICTION] == '':
            chg_existing = True
            if k in reporting_table.index:
                existing_table.loc[k, net_lbls.CONVICTION] = reporting_table.loc[k, rep_lbls.CONVICTION]
            else:
                existing_table.loc[k, net_lbls.CONVICTION] = 'MISSING'
        # Check reporting date column
        if v[net_lbls.REPORT_DATE] == '':
            chg_existing = True
            if k in reporting_table.index:
                existing_table.loc[k, net_lbls.REPORT_DATE] = reporting_table.loc[k, rep_lbls.REPORT_DATE]
            else:
                existing_table.loc[k, net_lbls.REPORT_DATE] = 'MISSING'
    # Update existing sheet with changes if any
    if chg_existing:
        set_net_existing(existing_table)

    ### For any orders that have a stretch limit check for unfilled orders
    # TODO: add stretch limit orders feature

    ### If it is the end of the day then exit necessary trades
    # TODO: add end of day exit feature

    # Update trailing-stop order prices
    order_manager.update_trailing(latest)

    # Check for future orders that have met their price and time requirements and send them
    order_manager.execute_ready_orders(poll_data)

    # TODO: when adding on to a position, update any target or stop orders


print("Finished")
