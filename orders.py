from datetime import datetime, timedelta
from os.path import isfile
import cPickle as pickle
from random import randint

from copy import deepcopy
import pandas as pd
import re

import xlintegrator as xlint
rep_lbls = xlint.rep_lbls
net_lbls = xlint.net_lbls
CURRENCIES = xlint.CURRENCIES
import sys


ORDERS_FILENAME = 'saved_orders.pkl'
SYMBOLS = pd.read_excel('Shared Files\\MasterFileAT.xls', 'Link to Excel', index_col=0).dropna()


# TODO: need ability to cancel an order
class OrderManager(object):

    def __init__(self):
        self._orders = {}
        self._load_orders_from_file()
        self.net_positions = xlint.get_net_existing(exclude_squared=False)
        super(OrderManager, self).__init__()

    def _load_orders_from_file(self):
        if isfile(ORDERS_FILENAME):
            with open(ORDERS_FILENAME, 'rb') as orders_file:
                self._orders = pickle.load(orders_file)
        else:
            self._orders = {}

    def _save_orders_to_file(self):
        if len(self._orders) > 0:
            with open(ORDERS_FILENAME, 'wb') as orders_file:
                pickle.dump(self._orders, orders_file)

    # TODO: test update trailing-stop future orders
    def update_trailing(self, latest):
        for order in self._orders.values():
            if order.trail_pct != 0:
                last = latest.loc[SYMBOLS.loc[order.company, 'eSignal Tickers'], 'Last']
                # If the price is greater than 1% different from stop price, update price
                if abs(1 - last / order.price) > 0.01:
                    if order.side == 1:
                        order.price = round(1.01 * last, 2)
                    else:
                        order.price = round(0.99 * last, 2)

    # TODO: execute_ready_orders
    def execute_ready_orders(self, poll_data):
        net_positions = xlint.get_net_existing(exclude_squared=False)
        # Send each order that is not complete and ready
        for k in self._orders.keys():
            if not self._orders[k].is_complete:
                if self._orders[k].is_order_ready(poll_data):
                    next_order = self._orders[k].get_next()
                    order_id = OrderManager.send_saxo_order(next_order)
                    if order_id is not None:
                        self._orders[k].ids.append(order_id)

        # Check if orders were filled and how much
        all_positions = xlint.get_all_existing()
        sent_orders = xlint.get_working_orders()
        for k in self._orders.keys():
            if not self._orders[k].is_complete:
                if OrderManager.is_filled(self._orders[k], net_positions, sent_orders, all_positions):
                    self._orders[k].is_complete = True

        self.net_positions = net_positions

        # # Check for future orders that have met their price and time requirements and send them
        # for order in self._orders[::-1]:
        #     comp = order['company']
        #     symbol = SYMBOLS.loc[comp, 'eSignal Tickers']

               # If order has met its price and valid_from requirements execute them
        #     if (((poll_data[symbol].iloc[-1]['Last'] <= order['price'] and order['side'] == 1) or
        #             (poll_data[symbol].iloc[-1]['Last'] >= order['price'] and order['side'] == 2)) and
        #             datetime.now().date() >= order['valid_from']):
        #         if 'limit' in order['order_type']:
        #             order_type = 'Limit'
        #         elif 'limit' in order['order_type']:
        #             order_type = 'Market'
        #         else:
        #             print('[WARNING] future order not placed! order_type=%s is not valid. Must contain limit or market.' % order['order_type'])
        #             continue
        #         self.send_saxo_order(company=comp,
        #                              asset_type='CfdOnStock',
        #                              trade_amt=order['trade_amt'],
        #                              side=order['side'],
        #                              duration='DayOrder',
        #                              order_type=order_type,
        #                              price=order['price']
        #                              )
        #         # Remove sent orders
        #         self._orders.remove(order)

    @staticmethod
    def is_filled(order, net_positions, sent_orders, all_positions):
        esig = SYMBOLS.loc[order.company, 'eSignal Tickers']
        saxo = SYMBOLS.loc[order.company, 'Saxo Tickers']

        # Check if this order has been sent
        if len(order.ids) > 0:
            order_id = order.ids[-1]
        else:
            return False

        # If the order id is in the sent orders and not all positions then get the amount filled the return is_filled as false
        if order_id in sent_orders.index and order_id not in all_positions.index:
            # TODO: make sure the type matches up here
            amt = sent_orders.loc[(sent_orders.index == order_id), 'FilledAmount'].squeeze()
            amt = 0 if amt == '' else int(amt)
            # if isinstance(order, TrancheOrder):
            order.filled_amt = sum(order.prev_trades) + amt
            print('[INFO] waiting on order for company=%s to fill, %s/%s' % (order.company, order.filled_amt, order.trade_size))
            return False
        # If the order it is not in the sent order but is in all positions then assume filled and set filled amount
        elif order_id not in sent_orders.index and order_id in all_positions.index:
            amt = abs(int(all_positions.loc[(all_positions.index == order_id), 'Amount'].squeeze()))
            order.prev_trades.append(amt)
            order.filled_amt = sum(order.prev_trades)
            order.trade_times.append(all_positions.loc[(all_positions.index == order_id), 'ExecutionTimeOpen'].squeeze())
            print('[INFO] order for company=%s is filled=%s, %s/%s' % (order.company, order.prev_trades[-1], order.filled_amt, order.trade_size))
            order.in_progress = False
            # Return filled=true if the entire trade size has been filled, but not if only a partial tranche fill
            if order.filled_amt == order.trade_size:
                return True
            else:
                return False
        else:
            raise Exception('[Critical] a sent order was not found in Order or All Positions')

    @staticmethod
    def send_saxo_order(order):

        # Convert side to string format
        if order.side == 1 or order.side == '1':
            side_str = 'Buy'
        elif order.side == 2 or order.side == '2':
            side_str = 'Sell'
        else:
            print('[WARNING] Value passed for order side is not valid, ORDER NOT SENT!')
            return

        # Create Saxo order function text
        order_msg = '=OpenApiPlaceOrder("{}","{}","{}",{},"{}","{}","{}",{}'.format(xlint.Config.SAXO_ACCT_KEY,
                                                                                    SYMBOLS.loc[order.company, 'Saxo Tickers'],
                                                                                    order.asset_type,
                                                                                    order.trade_size,
                                                                                    side_str,
                                                                                    order.valid_until,
                                                                                    order.order_type,
                                                                                    round(order.price, 2))
        # Add take profit and stop loss parameters
        # if order.take_profit is not None:
        #     order_msg += ',%s' % round(order.take_profit, 2)
        # if order.stop is not None:
        #     order_msg += ',{},"{}"'.format(round(order.stop, 2), order.stop_type)
        order_msg += ')'

        # Alter the message to indicate it is simulated if so
        if not xlint.Config.SAXO_ENABLED:
            alt_order_msg = "SIM#%s" % randint(100000, 999999)
        else:
            alt_order_msg = order_msg

        order_res = xlint.send_order(order.company, order_msg, alt_order_msg)

        # Set the order id
        if 'Order placed successfully' in order_res:
            order_id = re.search(r':([\d]+).', order_res).group(1)
        else:
            order_id = None
            print('[ERROR] send_saxo_order() - %s' % order_res)
            return

        # Mark order in progress
        order.in_progress = True

        if not xlint.Config.SAXO_ENABLED:
            print("The following SIMULATED order has been sent: %s" % order_msg)
        else:
            print("The following order has been sent: %s" % order_msg)

        return order_id

    def check_for_opening_orders(self):
        prev_close = xlint.get_prev_close()
        latest = xlint.get_latest()

        # TODO: switch prev_close_rep to prev_close
        # If certain conditions are met then make an order
        for k, v in xlint.get_reporting().iterrows():

            # If values have been entered for, Buy/Sell, % Limit, Trade Amount, and one of the exit columns (target%, stop, EOD) then create an order
            if (v[rep_lbls.LIMIT_PCT] != "" and v[rep_lbls.TRADE_AMT] != "" and
                    (v[rep_lbls.BUY_SELL] == 1 or v[rep_lbls.BUY_SELL] == 2) and
                    (v[rep_lbls.TARGET_PCT] != "" or v[rep_lbls.STOP_LOSS] != "" or v[rep_lbls.EOD_EXIT] != "")):

                company = SYMBOLS.loc[(SYMBOLS['eSignal Tickers'] == k)].index[0]
                side = v[rep_lbls.BUY_SELL]

                # If the limit-pct = 0 then do a market order, using the last price later for calculating position size
                if v[rep_lbls.LIMIT_PCT] == 0.0:
                    order_type = 'Market'
                    price = latest.loc[k, 'Last']
                # If the limit-pct > .5 then assume it is a price not a percent and do a limit order at that price
                elif v[rep_lbls.LIMIT_PCT] > 0.5:
                    order_type = 'Limit'
                    price = v[rep_lbls.LIMIT_PCT]
                # Otherwise limit-pct is assumed to be a percentage so calculate the limit price from that percent
                elif -0.5 < v[rep_lbls.LIMIT_PCT] < 0.5:
                    order_type = 'Limit'
                    # Calculate the limit price based off of the close previous to reporting day
                    price = (1 + v[rep_lbls.LIMIT_PCT]) * prev_close.loc[k, 'Last']
                else:
                    print('[ERROR] check_for_opening_orders - could not calculate price, LIMIT_PCT=%s' % v[rep_lbls.LIMIT_PCT])
                    return

                # Calculate the trade size
                trade_size = get_size_from_amt(company, v[rep_lbls.TRADE_AMT], price)

                # TODO: fix stop loss so that it uses our custom order objects
                # Calculate the stop loss
                stop_str = v[rep_lbls.STOP_LOSS]
                if stop_str != '' and stop_str != 0 and not None:
                    multiplier = 1.0 if v[rep_lbls.BUY_SELL] == 2 else -1.0
                    try:
                        stop_loss = price * (1 + multiplier * abs(float(stop_str)))
                    except:
                        stop_loss = None
                        print('[ERROR] "%s" is not a valid stop loss value' % stop_str)
                else:
                    stop_loss = None

                # Define the target% tranche orders for later if needed
                target_str = v[rep_lbls.TARGET_PCT]
                if target_str != '' and not None:
                    # tranche_cnt = (v[rep_lbls.TRADE_AMT] / xlint.TRANCHE_SZ.loc[k])
                    # start_range = -tranche_cnt + int(.5 * tranche_cnt + .5)
                    # end_range = tranche_cnt - int(.5 * tranche_cnt)
                    multiplier = 1.0 if v[rep_lbls.BUY_SELL] == 1 else -1.0

                    # Get target float value
                    try:
                        target_flt = abs(float(target_str))
                    except:
                        print('[ERROR] "%s" is not a valid target percent value, order not sent, please correct this' % target_str)
                        return

                    # If target-pct > .5 then assume it is a limit price
                    if target_flt > 0.5:
                        target_price = target_flt
                    # If target-pct > 0 and < .5 then assume it is percent and caculate price based on percent of prev close
                    elif -0.5 < target_flt < 0.5:
                        target_price = (1. + target_flt * multiplier) * prev_close.loc[k, 'Last']
                    else:
                        print('[ERROR] check_for_opening_orders() - could not calculate price, target_flt=%s' % target_flt)
                        return

                    # Get target_side
                    if side == 1 or side == '1':
                        target_side = 2
                    elif side == 2 or side == '2':
                        target_side = 1
                    else:
                        target_side = None

                    # Add tranche orders for later execution
                    self.add_order(TrancheOrder(
                        company=company,
                        side=target_side,
                        trade_size=trade_size,
                        price=target_price,
                        order_type=xlint.Config.TARGET_ORDER_TYPE,
                        is_entry=False,
                        tranche_gap=xlint.Config.TRANCHE_GAP if xlint.Config.TRANCHE_GAP is None else 0.0,
                        is_stop=False
                    ))


                # If a re-rater/de-rater or strong conviction set duration to good til canceled
                if v[rep_lbls.CONVICTION].lower() in ['r', 'd', 'se', 'sent']:
                    duration = 'GTC'
                else:
                    duration = 'DayOrder'

                ## Send opening order (company, asset_type, trade_amt, side, duration="DayOrder", order_type="Market", price=0.0, take_profit=None, stop=None, stop_type="StopIfTraded")
                OrderManager.send_saxo_order(Order(
                    company=company,
                    side=side,
                    trade_size=trade_size,
                    price=price,
                    order_type=order_type,
                    is_entry=True,
                    valid_until=duration,
                    is_stop=False
                    ))

    def add_order(self, order):
        # Add the order, incrementing the highest id by 1
        if len(self._orders) == 0:
            self._orders[0] = order
        else:
            self._orders[max(self._orders.keys())+1] = order
        self._save_orders_to_file()

    def remove_order(self, order_id):
        # Delete the order and save the file
        del self._orders[order_id]
        self._save_orders_to_file()


class Order(object):

    def __init__(self, company, side, trade_size, price, order_type, is_entry, valid_from=datetime.now(),
                 valid_until='DayOrder', trail_pct=0.0, asset_type='CfdOnStock', is_stop=False, time_gap=5):
        self.company        = company
        self.trade_size     = trade_size
        self.side           = side
        self.price          = round(price, 1)
        self.order_type     = order_type
        self.valid_from     = valid_from
        self.valid_until    = valid_until
        self.trail_pct      = trail_pct
        self.asset_type     = asset_type
        self.is_stop        = True if trail_pct != 0 else is_stop
        self.in_progress    = False
        self.is_entry       = is_entry
        self.is_complete    = False
        self.ids            = []
        self.filled_amt     = 0
        self.prev_trades    = []
        self.trade_times    = []
        self.time_gap       = time_gap if isinstance(time_gap, timedelta) else timedelta(seconds=time_gap)

        super(Order, self).__init__()

    def is_order_ready(self, poll_data):
        # Check if the time and price requirements have been met for the order
        esig = SYMBOLS.loc[self.company, 'eSignal Tickers']
        last = poll_data.loc[esig, 'Last'].head(1).squeeze()
        is_ready = False
        time_now = datetime.now()
        if len(self.trade_times) > 0:
            time_to_check = self.trade_times[-1] + self.time_gap
        else:
            time_to_check = self.valid_from

        # If the time requirement is met
        if time_now >= time_to_check:
            # If we are long to enter and the last price is less than required
            if self.side == 1 and not self.is_stop and last <= self.price:
                is_ready = True
            # If we are short to enter and last price is greater than required
            elif self.side == 2 and not self.is_stop and last >= self.price:
                is_ready = True
            # If we are long to sell and the last price is greater than required
            elif self.side == 2 and not self.is_stop and last >= self.price:
                is_ready = True
            # If we are short to cover and the last price is less than required
            elif self.side == 1 and not self.is_stop and last <= self.price:
                is_ready = True
            # If we are short to cover with stop loss and the last price is greater than required
            elif self.side == 1 and self.is_stop and last >= self.price:
                is_ready = True
            # If we are long to sell with stop loss and the last price is less than required
            elif self.side == 2 and self.is_stop and last <= self.price:
                is_ready = True

        if is_ready:
            print('[INFO] order for company=%s is ready' % self.company)
        return is_ready

    def get_next(self):
        return self


class TrancheOrder(Order):

    TRANCHE_SIZES   = {'GBP': 4.3,
                       'SEK': 4.3,
                       'NOK': 4.3,
                       'SWX': 7.5,
                       'DKK': 5.0,
                       'EUR': 7.0}

    def __init__(self, company, side, trade_size, price, order_type, is_entry, valid_from=datetime.now(), valid_until='DayOrder',
                 trail_pct=0.0, asset_type='CfdOnStock', tranche_gap=0.0, is_stop=False, time_gap=5):
        # TODO: incorporate tranche gap etc
        self._tranche_gap = check_tranche_gap(tranche_gap)
        self.tranche_size = 10.0

        # Calculate the partial size using 10 as the tranche size and the conversion rate
        # Get the number of positions that are equal to 10k USD
        # Grab currency using the ig symbol
        ig_symbol = SYMBOLS.loc[company, 'IG Tickers']
        currency = xlint.EXCH_CODE.loc[ig_symbol.split('.')[-1], 'Currency']

        if currency == 'USD':
            conv_rate = 1
        else:
            conv_rate = xlint.CONV_RATE.loc[currency, 'Conversion Rate']

        # Calculate number of shares using the trade amount, conversion rate, and limit price
        if price != 0.0:
            self.partial_size = int((self.tranche_size * 1000.0 * conv_rate) / price)
        else:
            print(['[DEBUG] SAXO_CREATE_ORDER - must pass the limit or last price'])
            sys.exit()

        # Define the min_tranche based on currency
        if company in CURRENCIES.keys():
            self._min_tranche = check_min_tranche(TrancheOrder.TRANCHE_SIZES[CURRENCIES[company]])
        else:
            print('[WARNING] company=%s was not found in the CURRENCIES dictionary' % company)
            self._min_tranche = check_min_tranche(max(TrancheOrder.TRANCHE_SIZES.values()))
            print('[WARNING] using default min_tranche=%s', self._min_tranche)

        super(TrancheOrder, self).__init__(company, side, trade_size, price, order_type, is_entry, valid_from,
                                           valid_until, trail_pct, asset_type, is_stop, time_gap)

    def get_next(self):
        part_order = deepcopy(self)
        part_order.trade_size = min(self.partial_size, self.trade_size - self.filled_amt)
        return part_order
    # TODO: tranche orders can only place one saxo order at a time, if it is filled then send another

        # tranche_cnt = (v[rep_lbls.TRADE_AMT] / xlint.TRANCHE_SZ.loc[k])
        # start_range = -tranche_cnt + int(.5 * tranche_cnt + .5)
        # end_range = tranche_cnt - int(.5 * tranche_cnt)
        # # Create tranche orders to return as future orders
        # if target_price is not None:
        #     for i in range(start_range, end_range):
        #         self.add_order({
        #             'company': company,
        #             'trade_amt': xlint.TRANCHE_SZ.loc[k],
        #             'side': target_side,
        #             'price': (1 + i * xlint.Config.TRANCHE_GAP) * target_price,
        #             'valid_from': v[rep_lbls.REPORT_DATE],
        #             'order_type': 'target-limit'})


def check_tranche_gap(tranche_gap):
    assert isinstance(tranche_gap, float), '[CRITICAL] tranche_gap=%s must be float' % tranche_gap
    assert tranche_gap < .02, '[CRITICAL] tranche_gap=%s must be greater than .02' % tranche_gap
    return tranche_gap


def check_min_tranche(min_tranche):
    assert isinstance(min_tranche, (int, float)), '[CRITICAL] min_tranche=%s must be int or float' % min_tranche
    return min_tranche


def get_size_from_amt(company, trade_amt, price):
    # Grab currency using the ig symbol
    ig_symbol = SYMBOLS.loc[company, 'IG Tickers']
    currency = xlint.EXCH_CODE.loc[ig_symbol.split('.')[-1], 'Currency']

    # Get conversion rate
    if currency == 'USD':
        conv_rate = 1
    else:
        conv_rate = xlint.CONV_RATE.loc[currency, 'Conversion Rate']

    # Calculate number of shares using the trade amount, conversion rate, and limit price
    if price != 0.0:
        trade_size = int((trade_amt * 1000.0 * conv_rate) / price)
    else:
        print(['[DEBUG] get_size_from_amt - must pass the limit or last price'])
        sys.exit()

    return trade_size


def round5(price):
    price = round(price * 100)
    return int(5 * round(float(price)/5)) / 100.0
