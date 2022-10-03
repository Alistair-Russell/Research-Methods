"""Algorithmic Trading

This module is for basic trading functionality including implementations of delta hedging,
vix futures hedging, and pairs trading.
"""

__version__ = "0.1"
__author__ = "Alistair Russell"

import datetime as dt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from ib_insync import *


def bus_day_delta(future_date):
    today = dt.date.today()
    # REMOVE future_date=dt.datetime.strptime(future.lastTradeDateOrContractMonth, "%Y%m%d").date()
    future = dt.datetime.strptime(future_date, "%Y%m%d").date()
    return np.busday_count(today, future_date)


class BaseAlgo:
    """Base class for algorithmic trading"""

    def __init__(self, url="127.0.0.1", port=7497, client_id=1):
        """Initialize IB connection and create a contract for the underlying

        Args:
            url (str, optional): URL string for TWS or IB gateway. Defaults to "127.0.0.1"
            port (int, optional): Port number for TWS or IB gateway. Defaults to 7497
            client_id (int, optional): Client ID. Defaults to 1
        """
        # ibkr connection
        self.ibconn = IB()
        self.ibconn.connect(url, port, clientId=client_id)

    def __del__(self):
        """Disconnects the IBKR session before object deletion"""
        self.ibconn.disconnect()

    def market_order(self, contract, num, dryrun=False):
        """Place a market order for a given contract

        Args:
            contract (obj): contract object for the security to order
            num (int): the number of contracts to sell

        Returns:
            obj: a trade (or what-if trade) object if the order num is not 0, None otherwise.
        """
        if num > 0:
            order = MarketOrder("BUY", num)
        elif num < 0:
            order = MarketOrder("SELL", abs(num))
        else:
            return None

        if dryrun:
            return self.ibconn.whatIfOrder(contract, order)
        else:
            return self.ibconn.placeOrder(contract, order)


class DeltaHedgeAlgo(BaseAlgo):
    """(TA1) Class for pricing and hedging of SPY options"""

    def __init__(self, tic, **kwargs):
        """Initialize delta hedge algorithm for a given ticker

        Args:
            tic (string): A ticker for an option in the current portfolio
        """
        super(DeltaHedgeAlgo, self).__init__(**kwargs)

        # get current positions with matching ticker
        self.positions = [
            p for p in self.ibconn.positions() if p.contract.symbol == tic
        ]

        # filter for options and stocks with ticker
        self.opts = [p for p in self.positions if p.contract.secType == "OPT"]
        assert len(self.opts) <= 1
        self.stks = [p for p in self.positions if p.contract.secType == "STK"]
        assert len(self.stks) <= 1

        # initialize contracts
        self.stk_contract = Stock(tic, "SMART", "USD")

    def rebalance(self, dryrun=False):
        """Rebalances the initialized security to a delta neutral hedge

        Args:
            dryrun (bool, optional): Execute a what-if trade instead of a real one. Defaults to False.

        Returns:
            list: current portfolio positions
        """
        # check that open option position exists
        if len(self.opts) == 0:
            print("No open option position to hedge")
            return

        # get current option contract details and ticker
        [option] = self.opts
        contracts = self.ibconn.qualifyContracts(option.contract)
        self.ibconn.reqMarketDataType(4)
        [opt_ticker] = self.ibconn.reqTickers(*contracts)

        # get option delta from modelGreeks to calculate the delta neutral position
        delta = opt_ticker.modelGreeks.delta
        delta_neutral_pos = -round(option.position * delta * int(opt_ticker.multiplier))

        # determine the trade needed to reach the delta neutral position
        if len(self.stks) == 0:
            hedge = delta_neutral_pos
        else:
            [stk] = self.stks
            hedge = delta_neutral_pos - stk.position
        self.ibconn.qualifyContracts(self.stk_contract)

        # make the market order trade
        if abs(hedge) > 0:
            trade = self.market_order(self.stk_contract, hedge, dryrun=dryrun)
            if not dryrun:
                while not trade.isDone():
                    self.ibconn.waitOnUpdate()
            else:
                print(f"[DRYRUN] trade would have been: {trade}")
        else:
            print("Already delta-neutral, no trade required.")

        # return list of all current positions
        return self.ibconn.positions()


class VIXFuturesHedgeAlgo(BaseAlgo):
    """(TA2) Class for hedging of VIX futures with E-mini-S&P futures"""

    def __init__(self, vix_future_date, hedge_tic, **kwargs):
        super(VIXFuturesHedgeAlgo, self).__init__(**kwargs)

        # initialize vix spot and futures dictionaries
        self.ticker = hedge_tic
        self.vix_spot = {}
        self.vix_future = {}

        # request delayed market data
        self.ibconn.reqMarketDataType(4)

        # vix future contract for date provided
        future = Future("VIX", vix_future_date, "CFE")
        self.ibconn.qualifyContracts(future)
        [future_con] = self.ibconn.reqContractDetails(future)
        self.vix_future["contract"] = future_con
        [future_tic] = self.ibconn.reqTickers(future)
        self.vix_future["ticker"] = future_tic

        # construct backwardation signal
        index = Index("VIX")
        self.ibconn.qualifyContracts(index)
        [spot_con] = self.ibconn.reqContractDetails(index)
        self.vix_spot["contract"] = spot_con
        [spot_tic] = self.ibconn.reqTickers(index)
        self.vix_spot["ticker"] = spot_tic

    def _get_es_beta(self):
        ## Q4- E-mini and VIX Futures Historical Data
        today = dt.date.today()
        today_str = today.strftime("%m/%d/%Y")
        a_year_ago = today - dt.timedelta(days=365)
        a_year_ago_str = a_year_ago.strftime("%m/%d/%Y")

        # WSJ database didn't work for futures, I got the data from marketwatch for vx00 and es00
        vix_futures_data = pd.read_csv(
            "https://www.marketwatch.com/investing/future/vx00/downloaddatapartial?startdate="
            + a_year_ago_str
            + "%2000:00:00&enddate="
            + today_str
            + "%2000:00:00&daterange=d30&frequency=p1d&csvdownload=true&downloadpartial=false&newdates=false"
        )
        sp500_futures = pd.read_csv(
            "https://www.marketwatch.com/investing/future/es00/downloaddatapartial?startdate="
            + a_year_ago_str
            + "%2000:00:00&enddate="
            + today_str
            + "%2000:00:00&daterange=d30&frequency=p1d&csvdownload=true&downloadpartial=false&newdates=false"
        )
        # I will use open prices to calculate the percentage changes
        sample = pd.DataFrame(columns=["Date", "sp_mini_change", "vix_futures_change"])
        sample["Date"] = vix_futures_data["Date"]
        sample["sp_mini_change"] = (
            sp500_futures["Open"].str.replace(",", "").astype(float)
            / sp500_futures["Open"].str.replace(",", "").astype(float).shift(periods=-1)
            - 1
        )
        sample["vix_futures_change"] = (
            vix_futures_data["Open"] / vix_futures_data["Open"].shift(periods=-1) - 1
        )

        # regress change in vix futures on the change in the E-mini
        model = smf.ols("vix_futures_change~sp_mini_change", sample).fit()

        # get the model beta
        beta = model.params.values[1]
        return beta

    def hedge(self, future_es_date, dryrun=False):
        # get es pricing
        self.ibconn.reqMarketDataType(4)
        future = Future("ES", future_es_date, "GLOBEX")
        self.ibconn.qualifyContracts(future)
        [es_con] = self.ibconn.reqContractDetails(future)
        [es_tic] = self.ibconn.reqTickers(future)
        es_price = es_tic.last

        # calculate hedge amount
        beta = self._get_es_beta()
        hedge_amt = round(
            (beta * self.vix_future["ticker"].last * 1000)
            / (es_price * self.vix_future["contract"].minTick * 100)
        )

        # place hedge trade
        if abs(hedge_amt) > 0:
            trade = self.market_order(es_con, hedge_amt, dryrun=dryrun)
            if not dryrun:
                while not trade.isDone():
                    self.ibconn.waitOnUpdate()
            else:
                print(f"[DRYRUN] trade would have been: {trade}")
        else:
            print("Already hedged, no trade required.")

    def exit_positions(self):
        vix_pos = [
            p
            for p in self.ibconn.positions()
            if p.contract.secType == "FUT" and p.contract.symbol == "VIX"
        ]

        for f in vix_pos:
            d = dt.datetime.strptime(
                f.contract.lastTradeDateOrContractMonth, "%Y%m%d"
            ).date()
            days = bus_day_delta(d)
            daily_roll = (
                self.vix_future["ticker"].last - self.vix_spot["ticker"].last
            ) / days  # TODO make a daily roll fn

            is_contango_takeprofit = f.position < 0 and (days <= 9 or daily_roll < 0.05)
            is_backwardation_takeprofit = f.position > 0 and (
                days <= 9 or daily_roll > -0.05
            )

            # in either takeprofit scenario, liquidate the positions
            if is_contango_takeprofit or is_backwardation_takeprofit:
                trade = self.market_order(f.contract, -1 * f.position)
                # TODO: liquidate the es position
