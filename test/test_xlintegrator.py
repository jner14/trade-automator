from __future__ import absolute_import
from unittest import TestCase
from datetime import date, time, datetime, timedelta
try:
    from .. import xlintegrator as xlint
except:
    import xlintegrator as xlint
import pandas as pd
pd.set_option('expand_frame_repr', False)


class TestXLIntegrator(TestCase):

    @classmethod
    def setUpClass(cls):
        xlint.Config.get_config_options()
        super(TestXLIntegrator, cls).setUpClass()

    def test_symbols(self):
        CURRENCIES = {}
        for comp in xlint.SYMBOLS.index:
            try:
                CURRENCIES[comp] = xlint.EXCH_CODE.loc[xlint.SYMBOLS.loc[comp, 'IG'].split('.')[-1].upper(), 'Currency']
            except Exception as e:
                print(comp, list(xlint.SYMBOLS.loc[comp]), e)
        columns = xlint.SYMBOLS.columns
        self.assertTrue('eSignal' in columns and 'IG' in columns and 'Saxo' in columns)
        print(xlint.SYMBOLS.head(5))

    def test_field_labels(self):
        reporting = xlint.get_reporting()[xlint.rep_lbls.ALL_LBLS]
        print(xlint.rep_lbls.ALL_LBLS)
        print(xlint.rep_lbls.FLD_IDS)
        existing = xlint.get_net_existing()[xlint.net_lbls.ALL_LBLS[1:]]
        print(xlint.net_lbls.ALL_LBLS)
        print(xlint.net_lbls.VALID_LBLS)
        print(xlint.net_lbls.FLD_IDS)

    def test_get_reporting(self):
        reporting = xlint.get_reporting()
        self.assertIsNotNone(reporting)
        self.assertIsNot(len(reporting), 0)

    def test_get_net_positions(self):
        existing = xlint.get_net_existing()
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

    def test_get_working_orders(self):
        df = xlint.get_working_orders()
        print(df)

    def test_get_all_existing(self):
        df = xlint.get_all_existing()
        print(df)
