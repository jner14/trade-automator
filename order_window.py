import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QAction, QLineEdit, QLabel, QRadioButton, QMessageBox, \
    QDesktopWidget
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtGui import QIcon, QFont

# from xlintegrator import saxo_create_order
from orders import *

WINDOW_GAP = 20

# TODO: add time delay cancellation of manual order window of 15 minutes
class OrderWindow(QWidget):
    def __init__(self, company, side, last_price, is_entry=True, size=0):
        QWidget.__init__(self)
        self.title = 'Manual Order Execution'
        self.left = 10
        self.top = 10
        self.width = 265
        self.height = 230
        self.order_type = 'Limit'
        self.comp = company
        self.side = side
        self.last_price = last_price
        self.is_entry = is_entry
        self.size = size
        self.initUI()

    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.center()

        # Create Fonts
        font_label = QFont()
        font_label.setPointSize(11)
        font_textboxes = QFont()
        font_textboxes.setPointSize(11)
        font_buttons = QFont()
        font_buttons.setPointSize(11)

        # Create labels
        self.label_comp_side = QLabel('Company:    {}\nSide:           {}'.format(self.comp, 'Buy' if self.side == 1 else 'Sell'), self)
        self.label_comp_side.move(WINDOW_GAP, WINDOW_GAP - 10)
        self.label_comp_side.setFont(font_label)
        self.label_price = QLabel('Price', self)
        self.label_price.move(WINDOW_GAP, WINDOW_GAP + 45)
        self.label_price.setFont(font_label)
        self.label_size = QLabel('Size(KUSD)', self)
        self.label_size.move(WINDOW_GAP, WINDOW_GAP + 85)
        self.label_size.setFont(font_label)
        self.label_radio = QLabel('Order Type', self)
        self.label_radio.move(WINDOW_GAP, WINDOW_GAP + 125)
        self.label_radio.setFont(font_label)

        # Create textboxes
        self.textbox_price = QLineEdit(self)
        self.textbox_price.move(WINDOW_GAP + 90, WINDOW_GAP + 40)
        self.textbox_price.resize(100, 25)
        self.textbox_price.setFont(font_textboxes)
        self.textbox_trade_amt = QLineEdit(self)
        self.textbox_trade_amt.move(WINDOW_GAP + 90, WINDOW_GAP + 80)
        self.textbox_trade_amt.resize(100, 25)
        self.textbox_trade_amt.setFont(font_textboxes)

        # Create radio button
        radio_limit = QRadioButton("Limit", self)
        radio_limit.setChecked(True)
        radio_limit.order_type = "Limit"
        radio_limit.move(WINDOW_GAP + 90, WINDOW_GAP + 125)
        radio_limit.setFont(font_label)
        radio_limit.toggled.connect(self.on_radio_button_toggled)
        radio_market = QRadioButton("Market", self)
        radio_market.setChecked(False)
        radio_market.order_type = "Market"
        radio_market.move(WINDOW_GAP + 150, WINDOW_GAP + 125)
        radio_market.setFont(font_label)
        radio_market.toggled.connect(self.on_radio_button_toggled)

        # Create order button
        order_btn = QPushButton('Create Order', self)
        order_btn.setToolTip('Send manual order to Saxo')
        order_btn.move(WINDOW_GAP, WINDOW_GAP + 165)
        order_btn.clicked.connect(self.on_click_send)
        order_btn.setFont(font_buttons)

        # Create cancel button
        cancel_btn = QPushButton('Cancel', self)
        cancel_btn.setToolTip("Close manual order window")
        cancel_btn.move(WINDOW_GAP + 150, WINDOW_GAP + 165)
        cancel_btn.clicked.connect(self.on_click_cancel)
        cancel_btn.setFont(font_buttons)

        # Show qt window
        self.show()

    @pyqtSlot()
    def on_click_send(self):
        price = 0.
        trade_amt = 0.
        price_str = self.textbox_price.text()
        trade_amt_str = self.textbox_trade_amt.text()

        # Check input for errors
        if price_str == '' or trade_amt_str == '':
            QMessageBox.question(self, 'Input Error', 'Please ensure fields are not left blank', QMessageBox.Ok, QMessageBox.Ok)
            return
        try:
            price = float(price_str)
            trade_amt = float(trade_amt_str)
        except Exception as e:
            QMessageBox.question(self, 'Input Error', 'Please ensure only numerical values are entered', QMessageBox.Ok, QMessageBox.Ok)
            print('{}\n[ERROR] Price={} or Size={} contains non-numerical values'.format(e, price_str, trade_amt_str))
            return

        price = price if price != 0. else self.last_price
        # TODO: Do tranches if limit order
        trade_size = get_size_from_amt(self.comp, trade_amt, price) if self.size == 0 else self.size
        OrderManager.send_saxo_order(Order(
            company=self.comp,
            side=self.side,
            trade_size=trade_size,
            price=price,
            order_type=self.order_type,
            valid_until='DayOrder',
            is_entry=self.is_entry,
            is_stop=False
        ))
        print('Sent manual order to Saxo: company={}, side={}, order_type={}, price={}, size={}'.format(self.comp, self.side, self.order_type, price, trade_size))
        self.close()

    @pyqtSlot()
    def on_click_cancel(self):
        print('Closed manual order window')
        self.close()

    def on_radio_button_toggled(self):
        radiobutton = self.sender()
        order_type = radiobutton.order_type
        if radiobutton.isChecked():
            self.order_type = order_type
            if order_type == 'Market':
                self.textbox_price.setText('0')
                self.textbox_price.setDisabled(True)
            else:
                self.textbox_price.setDisabled(False)
            print("Selected order type is %s" % order_type)

    def center(self):
        # geometry of the main window
        qr = self.frameGeometry()

        # center point of screen
        cp = QDesktopWidget().availableGeometry().center()

        # move rectangle's center point to screen's center point
        qr.moveCenter(cp)

        # top left of rectangle becomes top left of window centering it
        self.move(qr.topLeft())


if __name__ == '__main__':
    from xlintegrator import Config, get_latest, get_net_existing, net_lbls
    Config.get_config_options()
    app = QApplication(sys.argv)
    comp = 'Vodafone'
    esig = SYMBOLS.loc[comp, 'eSignal']
    last = get_latest().loc[esig, 'Last']
    # td_size = get_net_existing().loc[esig, net_lbls.AMOUNT]
    ex = OrderWindow(company=comp, side=2, last_price=last, is_entry=True)  # , size=td_size)
    sys.exit(app.exec_())
