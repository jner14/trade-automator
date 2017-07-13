from time import sleep
from unittest import TestCase
from orders import *
from order_window import OrderWindow
from PyQt5.QtWidgets import QApplication


class TestOrderManager(TestCase):

    def test__load_orders_from_file1(self):
        om = OrderManager()
        print('Length of orders=%s' % len(om._orders))
        self.assertIs(len(om._orders), 0, 'Length of orders=%s' % len(om._orders))

    def test_add_order(self):
        om = OrderManager()
        om._orders = {}
        om.add_order(Order('fake company', 1, 100, 123.45, 'Limit', is_entry=True))
        print('Length of orders=%s' % len(om._orders))
        self.assertIs(len(om._orders), 1, 'Length of orders=%s' % len(om._orders))

    def test__save_orders_to_file(self):
        om = OrderManager()
        om._orders = {}
        om.add_order(Order('fake company', 1, 100, 123.45, 'Limit', is_entry=True))
        om._orders = {}
        om._load_orders_from_file()
        print('Length of orders=%s' % len(om._orders))
        self.assertIs(len(om._orders), 1, 'Length of orders=%s' % len(om._orders))

    def test_update_trailing(self):
        self.fail()

    def test_execute_ready_orders(self):
        self.fail()

    def test_send_saxo_order(self):
        self.fail()

    def test_check_for_opening_orders(self):
        om = OrderManager()
        om._orders = {}
        xlint.Config.get_config_options()
        om.check_for_opening_orders()
        print('Length of orders=%s' % len(om._orders))
        self.assertIs(len(om._orders), 1, 'Length of orders=%s' % len(om._orders))

    def test_remove_order(self):
        om = OrderManager()
        om._orders = {}
        om.add_order(Order('fake company', 1, 100, 123.45, 'Limit', is_entry=True))
        len1 = len(om._orders)
        om.remove_order(0)
        len2 = len(om._orders)
        self.assertNotEqual(len1, len2)



class TestOrder(TestCase):

    def test_order_1(self):
        self.fail()


class TestTrancheOrders(TestCase):

    def test_tranche_1(self):
        comp = 'Vodafone'
        order = TrancheOrder(comp, 1, 10000, 219, 'Market', is_entry=True)

    def test_tranche_2(self):
        comp = 'Vodafone'
        from xlintegrator import Config, get_latest, get_net_existing, net_lbls
        Config.get_config_options()
        om = OrderManager()
        om._orders = {}
        order = TrancheOrder(comp, 1, 10000, 220.65, 'Market', is_entry=False, is_stop=True)
        om.add_order(order)
        while order.trade_size > order.filled_amt:
            print("sleeping...")
            sleep(5)
            om.execute_ready_orders(xlint.get_latest())
        # app = QApplication(sys.argv)
        # esig = SYMBOLS.loc[comp, 'eSignal Tickers']
        # last = get_latest().loc[esig, 'Last']
        # # td_size = get_net_existing().loc[esig, net_lbls.AMOUNT]
        # ex = OrderWindow(company=comp, side=2, last_price=last, is_entry=True)  # , size=td_size)
        # sys.exit(app.exec_())
