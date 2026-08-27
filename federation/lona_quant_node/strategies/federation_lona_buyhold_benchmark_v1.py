import backtrader as bt

class FederationLonaBuyHoldBenchmark(bt.Strategy):
    params = (
        ('position_fraction', 0.95),
    )

    def __init__(self):
        self.order = None
        self.entered = False

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            if order.status == order.Completed and order.isbuy():
                self.entered = True
            self.order = None

    def next(self):
        if self.order or self.entered or self.position:
            return
        cash = self.broker.getcash()
        size = int((cash * self.p.position_fraction) / self.data.close[0])
        if size > 0:
            self.order = self.buy(size=size)
