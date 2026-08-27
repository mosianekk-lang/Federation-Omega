import backtrader as bt

class FederationLonaCanarySMARisk(bt.Strategy):
    params = (
        ('fast_period', 20),
        ('slow_period', 50),
        ('position_fraction', 0.95),
        ('stop_loss_pct', 0.08),
    )

    def __init__(self):
        self.fast = bt.indicators.SMA(self.data.close, period=self.p.fast_period)
        self.slow = bt.indicators.SMA(self.data.close, period=self.p.slow_period)
        self.cross = bt.indicators.CrossOver(self.fast, self.slow)
        self.order = None
        self.entry_price = None

    def notify_order(self, order):
        if order.status == order.Completed:
            if order.isbuy():
                self.entry_price = order.executed.price
            elif order.issell():
                self.entry_price = None
        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def next(self):
        if self.order:
            return

        if self.position and self.entry_price:
            if self.data.close[0] <= self.entry_price * (1.0 - self.p.stop_loss_pct):
                self.order = self.close()
                return

        if not self.position and self.cross[0] > 0:
            cash = self.broker.getcash()
            size = int((cash * self.p.position_fraction) / self.data.close[0])
            if size > 0:
                self.order = self.buy(size=size)
        elif self.position and self.cross[0] < 0:
            self.order = self.close()
