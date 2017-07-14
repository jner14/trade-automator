from datetime import datetime, timedelta
from os.path import isfile
import cPickle as pickle
from random import randint
from copy import deepcopy
from time import sleep
import pandas as pd
import re
import sys
import numpy as np
import xlintegrator as xlint
rep_lbls = xlint.rep_lbls
net_lbls = xlint.net_lbls
SYMBOLS = xlint.SYMBOLS
CURRENCIES = xlint.CURRENCIES
ORDERS_FILENAME = 'saved_orders.pkl'


# TODO: need ability to cancel an order
class OrderManager(object):

    def __init__(self):
        self._orders = {}
        self._load_orders_from_file()
        # self.net_positions = xlint.get_net_existing(exclude_squared=False)
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
                last = latest.loc[SYMBOLS.loc[order.company, 'eSignal'], 'Last']
                # If the price is greater than 1% different from stop price, update price
                if abs(1 - last / order.price) > 0.01:
                    if order.side == 1:
                        order.price = round_to_tick(1.01 * last, order.company)
                    else:
                        order.price = round_to_tick(0.99 * last, order.company)

    def execute_ready_orders(self, latest):
        # Send each order that is not complete and ready
        for k in self._orders.keys():
            if not self._orders[k].is_complete:
                if self._orders[k].is_order_ready(latest):
                    print('%s: %s' % (self._orders[k].company, latest.loc[SYMBOLS.loc[self._orders[k].company, 'eSignal'], 'Last']))
                    next_order = self._orders[k].get_next()
                    order_id = OrderManager.send_saxo_order(next_order)
                    if order_id is not None:
                        self._orders[k].in_progress = True
                        self._orders[k].ids.append(order_id)

        # Check if orders were filled and how much
        for k in self._orders.keys():
            if not self._orders[k].is_complete:
                if OrderManager.is_filled(self._orders[k]):
                    self._orders[k].is_complete = True

        # self.net_positions = net_positions
        self.update_queued_orders()
        self._save_orders_to_file()

    def cancel_null_orders(self):
        existing = xlint.get_net_existing(exclude_squared=False)
        for k, o in self._orders.iteritems():
            esig = SYMBOLS.loc[o.company, 'eSignal']
            if not o.is_entry and existing.loc[esig, net_lbls.AMOUNT] == 0:
                print('[INFO][OrderManager] Canceling order=%s because there is no current position to exit' % k)
                o.is_complete = True

    def update_queued_orders(self):
        df = pd.DataFrame(columns=['Company', 'Trade Size', 'Side', 'Price', 'Order Type', 'Valid From',
                                   'Valid Until', 'Trail %', 'Asset Type', 'Is Stop', 'In Progress',
                                   'Is Entry', 'Is Complete', 'IDs', 'Filled Amt', 'Prev Trades', 'Trade Times',
                                   'Time Gap'])
        for k, o in self._orders.iteritems():
            df.loc[k] = [o.company, o.trade_size, o.side, o.price, o.order_type, o.valid_from.replace(microsecond=0),
                         o.valid_until, o.trail_pct, o.asset_type, o.is_stop, o.in_progress, o.is_entry, o.is_complete,
                         str(o.ids), o.filled_amt, str(o.prev_trades), str(o.trade_times), o.time_gap.seconds]
        xlint.set_queued_orders(df)

    @staticmethod
    def is_filled(order):
        all_positions = xlint.get_all_existing()
        sent_orders = xlint.get_working_orders()
        esig = SYMBOLS.loc[order.company, 'eSignal']
        saxo = SYMBOLS.loc[order.company, 'Saxo']

        # Check if this order has been sent
        if len(order.ids) > 0:
            order_id = order.ids[-1]
        else:
            return False

        for i in range(20):

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
            print('[DEBUG] waiting for position with order id=%s to show up in All Positions' % order_id)
            sleep(.2)
            all_positions = xlint.get_all_existing()
            sent_orders = xlint.get_working_orders()


        raise Exception('[Critical] a sent order=%s was not found in Order or All Positions' % order_id)

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
                                                                                    SYMBOLS.loc[order.company, 'Saxo'],
                                                                                    order.asset_type,
                                                                                    order.trade_size,
                                                                                    side_str,
                                                                                    order.valid_until,
                                                                                    order.order_type,
                                                                                    round_to_tick(order.price, order.company))
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

                company = SYMBOLS.loc[(SYMBOLS['eSignal'] == k)].index[0]
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

                # Get exit_side
                if side == 1 or side == '1':
                    exit_side = 2
                elif side == 2 or side == '2':
                    exit_side = 1
                else:
                    exit_side = None

                # TODO: fix stop loss so that it uses our custom order objects
                # Calculate the stop loss and add to orders list
                stop_str = v[rep_lbls.STOP_LOSS]
                if stop_str != '' and stop_str != 0 and not None:
                    multiplier = 1.0 if v[rep_lbls.BUY_SELL] == 2 else -1.0
                    try:
                        stop_price = price * (1 + multiplier * abs(float(stop_str)))
                    except:
                        stop_price = None
                        print('[ERROR] "%s" is not a valid stop loss value' % stop_str)
                    self.add_order(TrancheOrder(
                        company=company,
                        side=exit_side,
                        trade_size=trade_size,
                        price=stop_price,
                        order_type=xlint.Config.STOP_ORDER_TYPE,
                        is_entry=False,
                        tranche_gap=xlint.Config.TRANCHE_GAP if xlint.Config.TRANCHE_GAP is None else 0.0,
                        is_stop=True
                        ))
                else:
                    stop_price = None

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

                    # Add tranche orders for later execution
                    self.add_order(TrancheOrder(
                        company=company,
                        side=exit_side,
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

                ## Send opening order
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

                # Update dashboard
                while True:
                    try:
                        # Remove order info from reporting tab
                        reporting = xlint.get_reporting()
                        esig_symbol = SYMBOLS.loc[company, "eSignal Tickers"]
                        reporting.loc[esig_symbol, rep_lbls.BUY_SELL] = "sent"
                        xlint.set_reporting(reporting)
                        break
                    except Exception as e:
                        xlint.exception_msg(e, 'reporting')

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
        self.price          = round_to_tick(price, company)
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

    def is_order_ready(self, latest):
        # Check if the time and price requirements have been met for the order
        esig = SYMBOLS.loc[self.company, 'eSignal']
        last = latest.loc[esig, 'Last'].head(1).squeeze()
        is_ready = False
        time_now = datetime.now()
        if len(self.trade_times) > 0:
            time_to_check = self.trade_times[-1] + self.time_gap
        else:
            time_to_check = self.valid_from

        # If the time requirement is met and another order isn't waiting to be filled
        if time_now >= time_to_check and not self.in_progress:
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
        ig_symbol = SYMBOLS.loc[company, 'IG']
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


        # for k, v in existing.iterrows():
        #     tranche_cnt = int(math.ceil(v[net_lbls.AMOUNT] * latest.loc[k, 'Last'] / TRANCHE_SZ.loc[k]))
        #     start_range = -tranche_cnt + int(.5 * tranche_cnt + .5)
        #     end_range = tranche_cnt - int(.5 * tranche_cnt)
        #     # Create tranche orders
        #     for i in range(start_range, end_range):
        #         company = SYMBOLS.loc[(SYMBOLS['eSignal'] == k)].index[0]
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

def check_tranche_gap(tranche_gap):
    assert isinstance(tranche_gap, float), '[CRITICAL] tranche_gap=%s must be float' % tranche_gap
    assert tranche_gap < .02, '[CRITICAL] tranche_gap=%s must be greater than .02' % tranche_gap
    return tranche_gap


def check_min_tranche(min_tranche):
    assert isinstance(min_tranche, (int, float)), '[CRITICAL] min_tranche=%s must be int or float' % min_tranche
    return min_tranche


def get_size_from_amt(company, trade_amt, price):
    # Grab currency using the ig symbol
    ig_symbol = SYMBOLS.loc[company, 'IG']
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


def round_to_tick(price, company):
    tick_group = xlint.TICK_GROUPS.loc[company]
    bin_id = np.digitize(price, xlint.TICK_BINS[tick_group]['bins'])
    tick_size = xlint.TICK_BINS[tick_group]['tick sizes'][bin_id]
    return round_n(price, tick_size)


def round_n(price, n):
    price = round(price * 100)
    n100 = n * 100.0
    return int(n100 * round(float(price)/n100)) / 100.0
