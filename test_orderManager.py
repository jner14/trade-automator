from unittest import TestCase
from orders import *


class TestOrderManager(TestCase):

    def test__load_orders_from_file1(self):
        om = OrderManager()
        print('Length of orders=%s' % len(om._orders))
        self.assertIs(len(om._orders), 0, 'Length of orders=%s' % len(om._orders))

    def test_add_order(self):
        om = OrderManager()
        om._orders = {}
        om.add_order(Order('fake company', 1, 100, 123.45, 'Limit'))
        print('Length of orders=%s' % len(om._orders))
        self.assertIs(len(om._orders), 1, 'Length of orders=%s' % len(om._orders))

    def test__save_orders_to_file(self):
        om = OrderManager()
        om._orders = {}
        om.add_order(Order('fake company', 1, 100, 123.45, 'Limit'))
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
        om.add_order(Order('fake company', 1, 100, 123.45, 'Limit'))
        len1 = len(om._orders)
        om.remove_order(0)
        len2 = len(om._orders)
        self.assertNotEqual(len1, len2)



class TestOrder(TestCase):

    def test_get_next(self):
        self.fail()
