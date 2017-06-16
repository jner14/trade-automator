import pandas as pd
# from py_qlink import QLinkConn
from time import sleep
from datetime import datetime, time, timedelta
from xlintegrator import get_reporting, get_latest, FieldLabels as labels, Config, set_reporting, \
    set_reporting_prev_close, get_existing, get_monitoring, L2_auto_trade, get_reporting_day, get_reporting_prev_close
from consolidation_breakout import consol_breakout
from trade_utils import change_time
import re


BAR_LABELS = ['Open', 'High', 'Low', 'Close', 'Volume']
POLL_LABELS = ['Last', 'Volume']
TIME_FORMAT = "%I:%M:%S %p"
UPDATE_INTERVAL = 15  # seconds

period = 1
poll_data = {}
first_run = True
bars = {}
while True:

    # Update config options
    Config.get_config_options()
    # TODO: considering monitoring tables and only updating their dependant tables when there are changes
    # Implied usage scenario: user starts app before market opens and it captures the last price and volume
    #    and then waits until it changes to record the first bar open then continues to check every 15 seconds
    #    updating the current bars high and low. Then if minute mod 5 == 0 then set close of current bar to the most
    #    recent last value, setting the current last as the open to a new bar.

    # Secondary usage scenario: user starts app during market hours.

    ### Wait until market opens
    time_now = datetime.now().time()
    first_second = time_now.second
    print("The time is %s" % time_now.strftime(TIME_FORMAT))

    # TODO: fix this for times when program is started after market hours have begun
    if time_now < change_time(Config.MARKET_OPEN, -1) or time_now > Config.MARKET_CLOSE:
        print("Market hours are configured as {} - {}".format(Config.MARKET_OPEN.strftime(TIME_FORMAT),
                                                              Config.MARKET_CLOSE.strftime(TIME_FORMAT)))
        prev_close = get_latest()
        print("Will proceed after market hours begin.")
    elif change_time(Config.MARKET_OPEN, -1) < time_now < Config.MARKET_OPEN:
        prev_close = get_latest()
        print("Beginning in less than one minute.")
    else:
        prev_close = get_reporting_prev_close()

    while (time_now < Config.MARKET_OPEN or time_now > Config.MARKET_CLOSE):
        # Update config options
        Config.get_config_options()
        if datetime.now().second == first_second:
            print('.')
        else:
            print("."),
        # Wait a second and check time again
        sleep(1)
        time_now = datetime.now().time()
    print('')

    ### Collect some data from excel and update empty reporting day fields
    # Get tables
    reporting_table = get_reporting()
    existing_table = get_existing()
    monitoring_table = get_monitoring()

    # Set reporting date to today's date if it is currently None or NaT, i.e. empty
    if Config.AUTO_REPORT_DATE:
        report_day = datetime.now().date()
        reporting_table[labels.REPORT_DATE] = \
            reporting_table[labels.REPORT_DATE].apply(lambda x: report_day if x is None or x is pd.NaT else x)
        set_reporting(reporting_table, [labels.REPORT_DATE])

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
    BAR_SIZE = 5
    if (time_now.minute % BAR_SIZE == 0 and (5 > time_now.second or time_now.second > 55)):

        # Create 5 minute bars at the end of every bar
        assert len(poll_data) > 0, "poll_data has not been gathered"
        for k, v in poll_data.iteritems():
            # Create empty DataFrames for any new symbols in poll_data
            # if k not in bars.keys():
            bars[k] = pd.DataFrame(columns=BAR_LABELS)
            # Resample poll_data into 5 minute bars
            resampled = v.resample('%dT' % BAR_SIZE)
            bars[k]['Open'] = resampled['Last'].first()
            bars[k]['High'] = resampled['Last'].max()
            bars[k]['Low'] = resampled['Last'].min()
            bars[k]['Close'] = resampled['Last'].last()
            bars[k]['Volume'] = resampled['Volume'].sum()
            # Fill empty bars with previous close
            nanMsk = bars[k]['Open'].isnull()
            bars[k]['Close'] = bars[k]['Close'].ffill()
            bars[k].loc[nanMsk, 'Open'] = bars[k].loc[nanMsk, 'Close']
            bars[k].loc[nanMsk, 'High'] = bars[k].loc[nanMsk, 'Close']
            bars[k].loc[nanMsk, 'Low'] = bars[k].loc[nanMsk, 'Close']

        # # Print time elapsed since starting marker
        # print('Time Elapsed: %s' % (datetime.now() - st))

        # Check for consolidation breakouts
        # TODO: got AssertionError: Can not find column header=Last. Required column headers: ['Open', 'High', 'Low', 'Last', 'Intraday_Time', 'Intraday_Date']
        # breakouts = {}
        # for k, v in bars.iteritems():
        #     breakouts[k] = []
        #     if len(v) >= 5:
        #         breakouts[k] = consol_breakout(v)

        reporting_table = get_reporting()

        # Check for price target met
        # pt_matches = reporting_table[labels.ENTRY_REQ].str.extract(r'price\(([\d.]+)\)', expand=True).dropna()
        # for k, v in pt_matches.iteritems():
        #     print(k, v)

        # Check for price move 1% or 2%
        for k, v in bars.iteritems():
            if k not in reporting_table.index: continue
            if .99 * prev_close.loc[k, 'Last'] > v.ix[-1, 'Close'] or v.ix[-1, 'Close'] > 1.01 * prev_close.loc[k, 'Last']:
                if "1%Change" not in reporting_table.loc[k, labels.TRIGGERS]:
                    if reporting_table.loc[k, labels.TRIGGERS] != "":
                        reporting_table.loc[k, labels.TRIGGERS] += ",1%Change"
                    else:
                        reporting_table.loc[k, labels.TRIGGERS] = "1%Change"

            if .98 * prev_close.loc[k, 'Last'] > v.ix[-1, 'Close'] or v.ix[-1, 'Close']  > 1.02 * prev_close.loc[k, 'Last']:
                if "2%Change" not in reporting_table.loc[k, labels.TRIGGERS]:
                    if reporting_table.loc[k, labels.TRIGGERS] != "":
                        reporting_table.loc[k, labels.TRIGGERS] += ",2%Change"
                    else:
                        reporting_table.loc[k, labels.TRIGGERS] = "2%Change"

        # for k, v in reporting_table.iterrows():
        #     price_req = re.(v[labels.ENTRY_REQ])
        #     if "price(" in v[labels.ENTRY_REQ].lower():


        # # For any new consolidation breakouts update Reporting sheet
        # for k, v in reporting_table.iterrows():
        #     if len(breakouts[k]) > 0 and breakouts[k].iloc[-1] == True:
        #         if reporting_table.loc[k, labels.TRIGGERS] != "":
        #             reporting_table.loc[k, labels.TRIGGERS] += ",ConBreak"
        #         else:
        #             reporting_table.loc[k, labels.TRIGGERS] = "ConBreak"
        set_reporting(reporting_table)

        # # If certain conditions are met then make an order using L2 Auto Trader
        # for k, v in reporting_table.iterrows():
        #     # If values have been entered for, Buy or Sell, % Limit, Target, and Trade Amount then create an order
        #     if (v[labels.LIMIT] != ""
        #         and v[labels.TARGET] != ""
        #         and v[labels.TRADE_SZ] != ""
        #         and (v[labels.BUY] != "" or v[labels.SELL] != "" )):


print("Finished")
