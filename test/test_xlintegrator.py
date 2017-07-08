from __future__ import absolute_import
from unittest import TestCase
from datetime import date, time, datetime, timedelta
try:
    from .. import xlintegrator as xlint
except:
    import xlintegrator as xlint


class TestXLIntegrator(TestCase):

    @classmethod
    def setUpClass(cls):
        xlint.Config.get_config_options()
        super(TestXLIntegrator, cls).setUpClass()

    def test_field_labels(self):
        reporting = xlint.get_reporting()[xlint.FieldLabels.ALL_LABELS]

    def test_get_reporting(self):
        reporting = xlint.get_reporting()
        self.assertIsNotNone(reporting)
        self.assertIsNot(len(reporting), 0)

    def test_get_net_positions(self):
        existing = xlint.get_net_positions()
        print('Existing Net Positions\n%s' % existing)

    def test_get_config_options(self):
        self.assertIsNotNone(xlint.Config.AUTO_SORT)
        self.assertIsNotNone(xlint.Config.AUTO_REPORT_DATE)
        self.assertIsNotNone(xlint.Config.MARKET_OPEN)
        self.assertIsNotNone(xlint.Config.MARKET_CLOSE)
        self.assertIsNotNone(xlint.Config.L2_ACCT)
        self.assertIsNotNone(xlint.Config.L2_ENABLED)

    def test_exception_msg(self):
        st = datetime.now()
        xlint.exception_msg("This is a fake error to test exceptiong_msg()", "This is a fake sheet")

    # def test_L2_auto_trade(self):
    #     labels = xlint.FieldLabels
    #     prev_close_rep = xlint.get_reporting_prev_close()
    #
    #     # If certain conditions are met then make an order using L2 Auto Trader
    #     for k, v in xlint.get_reporting().iterrows():
    #         # If values have been entered for, Buy/Sell, % Limit, Target, and Trade Amount then create an order
    #         if (v[labels.LIMIT_PCT] != "" and v[labels.TRADE_AMT] != ""  # and v[labels.TARGET] != ""
    #                 and (v[labels.BUY_SELL] == 1 or v[labels.BUY_SELL] == 2)):
    #             # Calculate the limit price based off of the close previous to reporting day
    #             if v[labels.BUY_SELL] == 1:
    #                 limit_price = (1 + .01 * v[labels.LIMIT_PCT]) * prev_close_rep.loc[k, 'Last']
    #             else:
    #                 limit_price = (1 - .01 * v[labels.LIMIT_PCT]) * prev_close_rep.loc[k, 'Last']
    #
    #             # Send order (company, side, price, trade_amt, order_type, good_til, expiry="", stop="")
    #             xlint.L2_auto_trade(company=xlint.SYMBOLS.loc[(xlint.SYMBOLS['eSignal Tickers'] == k)].index[0],
    #                                   side=v[labels.BUY_SELL],
    #                                   price=limit_price,
    #                                   trade_amt=v[labels.TRADE_AMT],
    #                                   order_type=2,  # Limit
    #                                   good_til=0,  # Day
    #                                   )
    #
    # def test_L2_get_status(self):
    #     # from xlintegrator import Config, L2_get_status
    #     # Config.get_config_options()
    #     xlint.L2_get_status()

    def test_get_reporting_prev_close(self):
        # from xlintegrator import get_reporting_prev_close, Config
        # xlint.Config.get_config_options()
        df = xlint.get_reporting_prev_close()
        self.assertTrue(len(df) > 0)

    def test_set_reporting_prev_close(self):
        df = xlint.set_reporting_prev_close()

    def test_get_prev_close(self):
        df = xlint.get_prev_close()
        print(df.head())

    def test_forex(self):
        print(xlint.CONV_RATE)
        print(xlint.EXCH_CODE)
