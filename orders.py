from datetime import datetime
from os.path import isfile
import cPickle as pickle
from random import randint

import pandas as pd
import xlintegrator as xlint
rep_lbls = xlint.rep_lbls
import sys


ORDERS_FILENAME = 'saved_orders.pkl'
SYMBOLS = pd.read_excel('Shared Files\\MasterFileAT.xls', 'Link to Excel', index_col=0).dropna()


class OrderManager(object):

    def __init__(self):
        self._load_orders_from_file()
        super(OrderManager, self).__init__()

    def _load_orders_from_file(self):
        if isfile(ORDERS_FILENAME):
            with open(ORDERS_FILENAME, 'rb') as orders_file:
                self.orders = pickle.load(orders_file)
        else:
            self.orders = []

    def _save_orders_to_file(self):
        if len(self.orders) > 0:
            with open(ORDERS_FILENAME, 'wb') as orders_file:
                pickle.dump(self.orders, orders_file)

    # TODO: test update trailing-stop future orders
    def update_trailing(self, latest):

        # Update trailing-stop order prices
        for order in self.orders:
            comp = order['company']
            if order['order_type'] in ['trailing-stop-market', 'trailing-stop-limit']:
                last = latest.loc[SYMBOLS.loc[comp, 'eSignal Tickers'], 'Last']
                # If the price is greater than 1% different from stop price, update price
                if abs(1 - last / order['price']) > 0.01:
                    if order['side'] == 1:
                        order['price'] = round(1.01 * last, 2)
                    else:
                        order['price'] = round(0.99 * last, 2)

    # TODO: test future orders
    def execute_ready_orders(self, poll_data):

        # Check for future orders that have met their price and time requirements and send them
        for order in self.orders[::-1]:
            comp = order['company']
            symbol = SYMBOLS.loc[comp, 'eSignal Tickers']
            if (((poll_data[symbol].iloc[-1]['Last'] <= order['price'] and order['side'] == 1) or
                    (poll_data[symbol].iloc[-1]['Last'] >= order['price'] and order['side'] == 2)) and
                    datetime.now().date() >= order['valid_from']):
                if 'limit' in order['order_type']:
                    order_type = 'Limit'
                elif 'limit' in order['order_type']:
                    order_type = 'Market'
                else:
                    print('[WARNING] future order not placed! order_type=%s is not valid. Must contain limit or market.' % order['order_type'])
                    continue
                self.saxo_create_order(company=comp,
                                       asset_type='CfdOnStock',
                                       trade_amt=order['trade_amt'],
                                       side=order['side'],
                                       duration='DayOrder',
                                       order_type=order_type,
                                       price=order['price']
                                       )
                # Remove sent orders
                self.orders.remove(order)

    @staticmethod
    def saxo_create_order(company, asset_type, trade_amt, side, duration="DayOrder", order_type="Market", price=0.0, take_profit=None, stop=None, stop_type="StopIfTraded"):

        # Grab currency using the ig symbol
        ig_symbol = SYMBOLS.loc[company, 'IG Tickers']
        currency = xlint.EXCH_CODE.loc[ig_symbol.split('.')[-1], 'Currency']

        if currency == 'USD':
            xlint.CONV_RATE = 1
        else:
            xlint.CONV_RATE = xlint.CONV_RATE.loc[currency, 'Conversion Rate']

        # Calculate number of shares using the trade amount, conversion rate, and limit price
        if price != 0.0:
            trade_size = int((trade_amt * 1000.0 * xlint.CONV_RATE) / price)
        else:
            print(['[DEBUG] SAXO_CREATE_ORDER - must pass the limit or last price'])
            sys.exit()

        # Get side string
        if side == 1 or side == '1':
            side_str = 'Buy'
        elif side == 2 or side == '2':
            side_str = 'Sell'
        else:
            print('[WARNING] Value passed for order side is not valid, ORDER NOT SENT!')
            return

        # Create Saxo order function text
        order_msg = '=OpenApiPlaceOrder("{}","{}","{}",{},"{}","{}","{}",{}'.format(xlint.Config.SAXO_ACCT_KEY,
                                                                                    SYMBOLS.loc[company, 'Saxo Tickers'],
                                                                                    asset_type,
                                                                                    trade_size,
                                                                                    side_str,
                                                                                    duration,
                                                                                    order_type,
                                                                                    round(price, 2))
        if take_profit is not None:
            order_msg += ',%s' % round(take_profit, 2)
        if stop is not None:
            order_msg += ',{},"{}"'.format(round(stop, 2), stop_type)
        order_msg += ')'

        # Alter the message to indicate it is simulated if so
        if not xlint.Config.SAXO_ENABLED:
            alt_order_msg = "SIM#%s" % randint(100000, 999999)
        else:
            alt_order_msg = order_msg

        xlint.send_order(company, order_msg, alt_order_msg)

        if not xlint.Config.SAXO_ENABLED:
            print("The following SIMULATED order has been sent: %s" % order_msg)
        else:
            print("The following order has been sent: %s" % order_msg)

    def check_for_opening_orders(self):
        prev_close = xlint.get_prev_close()

        # TODO: switch prev_close_rep to prev_close
        # If certain conditions are met then make an order
        for k, v in xlint.get_reporting().iterrows():

            # If values have been entered for, Buy/Sell, % Limit, Trade Amount, and one of the exit columns (target%, stop, EOD) then create an order
            if (v[rep_lbls.LIMIT_PCT] != "" and v[rep_lbls.TRADE_AMT] != "" and
                    (v[rep_lbls.BUY_SELL] == 1 or v[rep_lbls.BUY_SELL] == 2) and
                    (v[rep_lbls.TARGET_PCT] != "" or v[rep_lbls.STOP_LOSS] != "" or v[rep_lbls.EOD_EXIT] != "")):

                company = SYMBOLS.loc[(SYMBOLS['eSignal Tickers'] == k)].index[0]
                side = v[rep_lbls.BUY_SELL]

                # Calculate the limit price based off of the close previous to reporting day
                limit_price = (1 + v[rep_lbls.LIMIT_PCT]) * prev_close.loc[k, 'Last']

                # Calculate the stop loss
                stop_str = v[rep_lbls.STOP_LOSS]
                if stop_str != '' and stop_str != 0 and not None:
                    multiplier = 1.0 if v[rep_lbls.BUY_SELL] == 2 else -1.0
                    try:
                        stop_loss = limit_price * (1 + multiplier * abs(float(stop_str)))
                    except:
                        stop_loss = None
                        print('[ERROR] "%s" is not a valid stop loss value' % stop_str)
                else:
                    stop_loss = None

                # Define the target % future orders
                target_str = v[rep_lbls.TARGET_PCT]
                if target_str != '' and target_str != 0 and not None:
                    tranche_cnt = (v[rep_lbls.TRADE_AMT] / xlint.TRANCHE_SZ.loc[k])
                    start_range = -tranche_cnt + int(.5 * tranche_cnt + .5)
                    end_range = tranche_cnt - int(.5 * tranche_cnt)
                    multiplier = 1.0 if v[rep_lbls.BUY_SELL] == 1 else -1.0
                    # Get target_side
                    if side == 1 or side == '1':
                        target_side = 2
                    elif side == 2 or side == '2':
                        target_side = 1
                    else:
                        target_side = None
                    # Get target float value
                    try:
                        target_flt = abs(float(target_str))
                        target_price = (1. + target_flt * multiplier) * prev_close.loc[k, 'Last']
                    except:
                        target_price = None
                        print('[ERROR] "%s" is not a valid target percent value' % target_str)
                    # Create tranche orders to return as future orders
                    if target_price is not None:
                        for i in range(start_range, end_range):
                            self.orders.append({
                                'company': company,
                                'trade_amt': xlint.TRANCHE_SZ.loc[k],
                                'side': target_side,
                                'price': (1 + i * xlint.Config.TRANCHE_GAP) * target_price,
                                'valid_from': v[rep_lbls.REPORT_DATE],
                                'order_type': 'target-limit'})

                # Send order (company, asset_type, trade_amt, side, duration="DayOrder", order_type="Market", price=0.0, take_profit=None, stop=None, stop_type="StopIfTraded")
                OrderManager.saxo_create_order(company=company,
                                               asset_type='CfdOnStock',
                                               trade_amt=v[rep_lbls.TRADE_AMT],
                                               side=side,
                                               duration='DayOrder',
                                               order_type='Limit',
                                               price=limit_price,
                                               stop=stop_loss,
                                               )


class Order(object):

    def __init__(self, company, trade_size, side, price, order_type, valid_from=datetime.now(), valid_until='DayOrder', trail_pct=0.0):
        self.company        = company
        self.trade_size     = trade_size
        self.side           = side
        self.price          = price
        self.order_type     = order_type
        self.valid_from     = valid_from
        self.valid_until    = valid_until
        self.trail_pct      = trail_pct

        super(Order, self).__init__()


class TrancheOrder(Order):

    TRANCHE_SIZES   = {'GBP': 4.3,
                       'SEK': 4.3,
                       'NOK': 4.3,
                       'SWX': 7.5,
                       'DKK': 5.0,
                       'EUR': 7.0}
    CURRENCIES      = {}

    def __init__(self, company, trade_size, side, price, order_type, tranche_gap=0.0, valid_from=datetime.now(), valid_until='DayOrder', trail_pct=0.0):
        self._tranche_gap = check_tranche_gap(tranche_gap)

        # Define the min_tranche based on currency
        if company in TrancheOrder.CURRENCIES.keys():
            self._min_tranche = check_min_tranche(TrancheOrder.TRANCHE_SIZES[TrancheOrder.CURRENCIES[company]])
        else:
            print('[WARNING] company=%s was not found in the CURRENCIES dictionary' % company)
            self._min_tranche = check_min_tranche(max(TrancheOrder.TRANCHE_SIZES.values()))
            print('[WARNING] using default min_tranche=%s', self._min_tranche)

        super(TrancheOrder, self).__init__(company, trade_size, side, price, order_type, valid_from, valid_until, trail_pct)


def check_tranche_gap(tranche_gap):
    assert isinstance(tranche_gap, float), '[CRITICAL] tranche_gap=%s must be float'
    return tranche_gap


def check_min_tranche(min_tranche):
    assert isinstance(min_tranche, (int, float)), '[CRITICAL] min_tranche=%s must be int or float'
    return min_tranche


class FixedOrder(Order):
    def __init__(self, company, trade_size, side, price, order_type, valid_from=datetime.now(), valid_until='DayOrder',
                 trail_pct=0.0):
        super(FixedOrder, self).__init__(company, trade_size, side, price, order_type, valid_from, valid_until, trail_pct)


class OrderByAmount(Order):
    def __init__(self, company, trade_amt, side, price, order_type, valid_from=datetime.now(), valid_until='DayOrder',
                 trail_pct=0.0):

        super(OrderByAmount, self).__init__(company, trade_size, side, price, order_type, valid_from, valid_until, trail_pct)