import pandas as pd
# from py_qlink import QLinkConn
from time import sleep
from datetime import datetime, time, timedelta
from xlintegrator import get_reporting, get_latest, FieldLabels as labels, Config, set_reporting, L2_get_status, \
    set_reporting_prev_close, get_existing, get_monitoring, L2_auto_trade, get_reporting_day, get_reporting_prev_close, \
    get_prev_close, CONV_RATE, EXCH_CODE, SYMBOLS, saxo_create_order
from algos import consolidation_breakout
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

    # # TODO: fix this for times when program is started after market hours have begun
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

    # Waiting
    orders_sent = False
    while (time_now < Config.MARKET_OPEN or time_now > Config.MARKET_CLOSE):

        # # Send orders to L2 Auto Trade 3 seconds before the open
        # if Config.MARKET_OPEN > time_now > change_time(Config.MARKET_OPEN, -1) and not orders_sent:
        #     seconds_before = 3.0
        #     time_left = 60.0 - seconds_before - time_now.second + time_now.microsecond / 1e6
        #     print("\nExecuting orders in %s seconds" % time_left)
        #     sleep(time_left)
        #     print("The time is %s" % datetime.now().strftime(TIME_FORMAT))
        #     print("Executing orders...")
        #     # If certain conditions are met then make an order using L2 Auto Trader
        #     for k, v in get_reporting().iterrows():
        #         # If values have been entered for, Buy/Sell, % Limit, Target, and Trade Amount then create an order
        #         if (v[labels.LIMIT_PCT] != "" and v[labels.TARGET] != "" and v[labels.TRADE_AMT] != ""
        #                 and (v[labels.BUY_SELL] == 1 or v[labels.BUY_SELL] == 2)):
        #             # Calculate the limit price based off of the close previous to reporting day
        #             if v[labels.BUY_SELL] == 1:
        #                 limit_price = (1 + .01 * v[labels.LIMIT_PCT]) * prev_close_rep.loc[k, 'Last']
        #             else:
        #                 limit_price = (1 - .01 * v[labels.LIMIT_PCT]) * prev_close_rep.loc[k, 'Last']
        #
        #             # Send order (company, side, price, trade_amt, order_type, good_til, expiry="", stop="")
        #             L2_auto_trade(company=SYMBOLS.loc[(SYMBOLS['eSignal Tickers'] == 'VOD-LON')].index[0],
        #                           side=v[labels.BUY_SELL],
        #                           price=limit_price,
        #                           trade_amt=v[labels.TRADE_AMT],
        #                           order_type=2,     # Limit
        #                           good_til=0,       # Day
        #                           )
        #     orders_sent = True
        #     print("The time is %s" % datetime.now().strftime(TIME_FORMAT))
        #     print("Finished...")

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
    BAR_SIZE = 5
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
            bars[k]['Volume'] = resampled['Volume'].sum()
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

        reporting_table = get_reporting()

        # Check for price target met
        # pt_matches = reporting_table[labels.ENTRY_REQ].str.extract(r'price\(([\d.]+)\)', expand=True).dropna()
        # for k, v in pt_matches.iteritems():
        #     print(k, v)

        # Check for price move 1% or 2%
        for k, v in bars.iteritems():
            if k not in reporting_table.index: continue
            try:
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
            except Exception as e:
                print(e)

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

        # If certain conditions are met then make an order using SAXO OpenAPI for excel
        # TODO: switch prev_close_rep to prev_close
        for k, v in get_reporting().iterrows():
            # If values have been entered for, Buy/Sell, % Limit, Target, and Trade Amount then create an order
            if (v[labels.LIMIT_PCT] != "" and v[labels.TRADE_AMT] != ""  # and v[labels.TARGET] != ""
                    and (v[labels.BUY_SELL] == 1 or v[labels.BUY_SELL] == 2)):
                # Calculate the limit price based off of the close previous to reporting day
                if v[labels.BUY_SELL] == 1:
                    limit_price = (1 + .01 * v[labels.LIMIT_PCT]) * prev_close_rep.loc[k, 'Last']
                else:
                    limit_price = (1 - .01 * v[labels.LIMIT_PCT]) * prev_close_rep.loc[k, 'Last']

                # Send order (company, asset_type, trade_amt, side, duration="DayOrder", order_type="Market", price=0.0, take_profit=None, stop=None, stop_type="StopIfTraded")
                saxo_create_order(company=SYMBOLS.loc[(SYMBOLS['eSignal Tickers'] == k)].index[0],
                                  asset_type='Stock',
                                  trade_amt=v[labels.TRADE_AMT],
                                  side=v[labels.BUY_SELL],
                                  duration='DayOrder',
                                  order_type='Limit',
                                  price=limit_price,
                                  )

print("Finished")
