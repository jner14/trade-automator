import py_dde_client as ddec
from datetime import datetime
import time
import pandas as pd


class QLinkConn(object):
    MAX_TRIES = 5
    WAIT = 1
    BAR_LABELS = {'d': 'Date',
                  't': 'Time',
                  'o': 'Open',
                  'h': 'High',
                  'l': 'Low',
                  'c': 'Close',
                  'v': 'Volume'}
    TRADE_LABELS = {'d': 'Date',
                    't': 'Time',
                    'c': 'BidAskTradeCodes',
                    'e': 'ExchangeCode',
                    'p': 'Price',
                    's': 'Size'}

    def __init__(self):
        self.bars_client = ddec.DDEClient('QLINK', 'bars')
        self.ts_client = ddec.DDEClient('QLINK', 'ts')
        self.snapshot_client = ddec.DDEClient('QLINK', 'snapshot')
        super().__init__()

    def get_bars(self, symbol, period=5, count=100, fields='DTOHLCV',
                 start_time='08:00', end_time='16:30', fill=True):
        """
            SYMBOL,PERIOD,#BARS,[DTOHLCV],{HH:MM-HH:MM},{FILL}
            Example: IBM,15,1000,DTOHLCV,09:30-16:00
        """

        # Create main request message
        message = "{},{},{},{}".format(symbol, period, count, fields)

        # Add start and end times if passed
        if start_time and end_time:
            message += ",{}-{}".format(start_time, end_time)

        # Add fill parameter if passed true
        if fill:
            message += ",FILL"

        response = None
        for i in range(QLinkConn.MAX_TRIES + 1, 0, -1):

            # Send request to QLink DDE server and decode response byte string
            response = self.bars_client.request(message).decode('utf-8')

            # Break from loop if response is not empty
            if response.count('\n') < len(response):
                print("QLinkConn-Bars(SUCCESS)")
                break

            # If response was empty then wait and try again
            if i <= QLinkConn.MAX_TRIES:
                print("QLinkConn-Bars(NO DATA RETURNED). Trying %s more time%s..." % (i-1, 's' if i > 1 else ''))
            time.sleep(QLinkConn.WAIT)

        # Get dtypes
        column_labels = [QLinkConn.BAR_LABELS[x.lower()] for x in fields]

        # Parse response
        bars = pd.DataFrame([bar_str.split('\t') for bar_str in response.split('\n')],
                            columns=column_labels).head(count)

        # Convert numerical types
        for f in fields:
            if f.lower() in ['o', 'h', 'l', 'c', 'v']:
                bars[QLinkConn.BAR_LABELS[f.lower()]] = pd.to_numeric(bars[QLinkConn.BAR_LABELS[f.lower()]])

        # Return bars
        return bars

    def get_trades(self, symbol, count=100, fields='DTPS'):
        """
            SYMBOL,#ROWS,[DTCEPS]
            Example: IBM,200,DTPSEC
        """

        # Create main request message
        message = "{},{},{}".format(symbol, count, fields)

        response = None
        for i in range(QLinkConn.MAX_TRIES + 1, 0, -1):

            # Send request to QLink DDE server and decode response byte string
            response = self.ts_client.request(message).decode('utf-8')

            # Break from loop if response is not empty
            if response.count('\n') < len(response):
                print("QLinkConn-Trades(SUCCESS)")
                break

            # If response was empty then wait and try again
            if i <= QLinkConn.MAX_TRIES:
                print("QLinkConn-Trades(NO DATA RETURNED). Trying %s more time%s..." % (i-1, 's' if i > 1 else ''))
            time.sleep(QLinkConn.WAIT)

        # Get dtypes
        column_labels = [QLinkConn.TRADE_LABELS[x.lower()] for x in fields]

        # Parse response
        trades = pd.DataFrame([bar_str.split('\t') for bar_str in response.split('\n')],
                              columns=column_labels).head(count)

        # Convert numerical types
        for f in fields:
            if f.lower() in ['p', 's']:
                trades[QLinkConn.TRADE_LABELS[f.lower()]] = pd.to_numeric(trades[QLinkConn.TRADE_LABELS[f.lower()]])

        # Return trades
        return trades

    # def get_snapshot(self, ):
    #     """
    #         SYMBOL,#ROWS,[DTCEPS]
    #         Example: IBM,200,DTPSEC
    #     """
    #
    #     # Create main request message
    #     message = "{},{},{}".format(symbol, count, fields)
    #
    #     response = None
    #     for i in range(QLinkConn.MAX_TRIES + 1, 0, -1):
    #
    #         # Send request to QLink DDE server and decode response byte string
    #         response = self.ts_client.request(message).decode('utf-8')
    #
    #         # Break from loop if response is not empty
    #         if response.count('\n') < len(response):
    #             print("QLinkConn-Trades(SUCCESS)")
    #             break
    #
    #         # If response was empty then wait and try again
    #         if i <= QLinkConn.MAX_TRIES:
    #             print("QLinkConn-Trades(NO DATA RETURNED). Trying %s more time%s..." % (i-1, 's' if i > 1 else ''))
    #         time.sleep(QLinkConn.WAIT)
    #
    #     # Get dtypes
    #     column_labels = [QLinkConn.TRADE_LABELS[x.lower()] for x in fields]
    #
    #     # Parse response
    #     trades = pd.DataFrame([bar_str.split('\t') for bar_str in response.split('\n')],
    #                           columns=column_labels).head(count)
    #
    #     # Convert numerical types
    #     for f in fields:
    #         if f.lower() in ['p', 's']:
    #             trades[QLinkConn.TRADE_LABELS[f.lower()]] = pd.to_numeric(trades[QLinkConn.TRADE_LABELS[f.lower()]])
    #
    #     # Return snapshot
    #     return snapshot


class OldDDEConn(object):
    FIELDS = ['open', 'high', 'low', 'last', 'totalvol', 'date', 'time']

    def __init__(self, symbol):
        self.symbol = symbol
        self.clients = {}

    def get_open(self):
        if 'open' not in self.clients.keys():
            self.clients['open'] = ddec.DDEClient('WINROS', 'open')
        return self.clients['open'].request(self.symbol)

    def get_high(self):
        if 'high' not in self.clients.keys():
            self.clients['high'] = ddec.DDEClient('WINROS', 'high')
        return self.clients['high'].request(self.symbol)

    def get_low(self):
        if 'low' not in self.clients.keys():
            self.clients['low'] = ddec.DDEClient('WINROS', 'low')
        return self.clients['low'].request(self.symbol)

    def get_last(self):
        if 'last' not in self.clients.keys():
            self.clients['last'] = ddec.DDEClient('WINROS', 'last')
        return self.clients['last'].request(self.symbol)

    def get_totalvol(self):
        if 'totalvol' not in self.clients.keys():
            self.clients['totalvol'] = ddec.DDEClient('WINROS', 'totalvol')
        return self.clients['totalvol'].request(self.symbol)

    def get_other(self, field):
        if field in self.clients.keys():
            return self.clients[field].request(self.symbol)
        elif field in OldDDEConn.FIELDS:
            self.clients[field] = ddec.DDEClient('WINROS', field)
            return self.clients[field].request(self.symbol)
        else:
            print("'%s' is not in the list of acceptable fields: %s" % (field, OldDDEConn.FIELDS))
            return None

if __name__ == "__main__":

    st = datetime.now()

    symbol = 'VOD-LON'
    qlink = QLinkConn()
    bars1 = qlink.get_bars(symbol, count=500, period=5)
    trades1 = qlink.get_trades(symbol, count=500)

    print('Time Elapsed: %s' % (datetime.now() - st))

    print("Finished")
