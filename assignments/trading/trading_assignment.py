"""Algorithmic Trading

This module is for basic trading functionality including implementations of delta hedging,
vix futures hedging, and pairs trading.
"""

__version__ = "0.1"
__author__ = "Alistair Russell"

from ast import literal_eval
import datetime as dt
import numpy as np
import pandas as pd
import pandas_datareader as pdr
import statsmodels.api as sm
import statsmodels.formula.api as smf
import itertools as it
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

        # account value
        act = self.ibconn.accountSummary()
        self.portfolio_val = float(act[19].value)

        # max position size
        self.max_position = 0.05 * self.portfolio_val

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
        multiplier = int(opt_ticker.contract.multiplier)
        delta_neutral_pos = -round(option.position * delta * multiplier)

        # determine the trade needed to reach the delta neutral position
        if len(self.stks) == 0:
            hedge = delta_neutral_pos
        else:
            [stk] = self.stks
            hedge = delta_neutral_pos - stk.position
        self.ibconn.qualifyContracts(self.stk_contract)

        # make the market order trade
        is_close_to_ATM = (delta >= 0.4 or delta <= 0.6) and hedge > 0
        is_far_from_ATM = (delta < 0.4 or delta > 0.6) and hedge > 10
        if is_close_to_ATM or is_far_from_ATM:
            trade = self.market_order(self.stk_contract, hedge, dryrun=dryrun)
            if not dryrun:
                while not trade.isDone():
                    self.ibconn.waitOnUpdate()
            else:
                print(f"[DRYRUN] delta neutral is: SPY {delta_neutral_pos}")
                print(f"[DRYRUN] trade would have been: SPY {hedge}")
        else:
            print("Already delta-neutral, no trade required.")

        # return list of all current positions

        return self.ibconn.positions()


class VIXFuturesHedgeAlgo(BaseAlgo):
    """(TA2) Class for hedging of VIX futures with E-mini-S&P futures"""

    def __init__(self, vix_future_date, es_future_date, **kwargs):
        super(VIXFuturesHedgeAlgo, self).__init__(**kwargs)

        # initialize vix spot and futures dictionaries
        self.vix_spot = {}
        self.vix_future = {}
        self.es_future = {}

        # request delayed market data
        self.ibconn.reqMarketDataType(4)

        # vix future contract for date provided
        future = Future("VIX", vix_future_date, "CFE")
        self.ibconn.qualifyContracts(future)
        [future_con] = self.ibconn.reqContractDetails(future)
        self.vix_future["contract"] = future_con
        [future_tic] = self.ibconn.reqTickers(future)
        self.vix_future["ticker"] = future_tic

        # vix spot contract for date provided
        index = Index("VIX")
        self.ibconn.qualifyContracts(index)
        [spot_con] = self.ibconn.reqContractDetails(index)
        self.vix_spot["contract"] = spot_con
        [spot_tic] = self.ibconn.reqTickers(index)
        self.vix_spot["ticker"] = spot_tic

        # es future contract for date provided
        es = Future("ES", es_future_date, "GLOBEX")
        self.ibconn.qualifyContracts(es)
        [es_con] = self.ibconn.reqContractDetails(es)
        self.es_future["contract"] = es_con
        [es_tic] = self.ibconn.reqTickers(es)
        self.es_future["ticker"] = es_tic

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

    def hedge(self, quantity, dryrun=False):
        # calculate hedge amount
        beta = self._get_es_beta()
        hedge_amt = (
            -1
            * quantity
            * round(
                (beta * float(self.vix_future["ticker"].last) * 1000)
                / (float(self.es_future["ticker"].last) * 50)
            )
        )

        # place hedge trade
        es_con = self.es_future["contract"].contract
        if abs(hedge_amt) > 0:
            print(f"Attempting to hedge with E-mini: amount {hedge_amt}")
            trade = self.market_order(es_con, hedge_amt, dryrun=dryrun)

            if not dryrun:
                while not trade.isDone():
                    self.ibconn.waitOnUpdate()
            else:
                print(f"[DRYRUN] trade would have been: {trade}")
        else:
            print("Already hedged, no trade required.")

    def enter_positions(self, quantity):
        # if there are open vix positions then return, otherwise attempt to enter
        vix_positions = [
            p for p in self.ibconn.positions() if p.contract.symbol == "VIX"
        ]
        if len(vix_positions) > 0:
            print(f"VIX positions already entered: {vix_positions}")
            return

        # get contract
        vix_con = self.vix_future["contract"].contract
        vixf_price = self.vix_future["ticker"].last
        vixs_price = self.vix_spot["ticker"].last

        # calculate the contango/backwardation signal
        signal = (vixf_price / vixs_price) - 1

        # calculate the daily roll
        future_date = vix_con.lastTradeDateOrContractMonth
        days = bus_day_delta(future_date)
        daily_roll = (vixf_price - vixs_price) / days

        # initial trade
        if signal < 0 and daily_roll < -0.10:
            print(
                "Market backwardation - daily roll is less than -0.10. Purchasing VIX Futures."
            )
            trade = self.market_order(vix_con, quantity)
            self.hedge(self, -1 * quantity)
        elif signal > 0 and daily_roll > 0.10:
            print(
                "Market contango - daily roll is more than 0.10. Shorting VIX Futures."
            )
            trade = self.market_order(vix_con, -1 * quantity)
            self.hedge(self, quantity)
        else:
            print(
                f"Signal is {signal} and daily roll is {daily_roll}. No action taken."
            )

    def exit_positions(self):
        f = [
            p
            for p in self.ibconn.positions()
            if p.contract.secType == "FUT" and p.contract.symbol == "VIX"
        ]
        e = [
            p
            for p in self.ibconn.positions()
            if p.contract.secType == "FUT" and p.contract.symbol == "ES"
        ]
        if len(f) == 0 and len(e) == 0:
            print("No positions to exit.")
            return
        elif len(f) == 0 or len(e) == 0:
            print(f"There are unhedged positions: {f} {e}.")
            print(
                "Please hedge manually or use VIXFuturesHedgeAlgo.hedge(position) and retry"
            )
            return

        # take the first positions
        vixf = f[0]
        esf = e[0]

        d = vixf.contract.lastTradeDateOrContractMonth
        days = bus_day_delta(d)
        daily_roll = (
            self.vix_future["ticker"].last - self.vix_spot["ticker"].last
        ) / days  # TODO make a daily roll fn

        is_contango_takeprofit = vixf.position < 0 and (days <= 9 or daily_roll < 0.05)
        is_backwd_takeprofit = vixf.position > 0 and (days <= 9 or daily_roll > -0.05)

        # in either takeprofit scenario, liquidate the positions
        if is_contango_takeprofit or is_backwd_takeprofit:
            print("Exiting VIX and ES positions")
            vixtrade = self.market_order(vixf.contract, -1 * vixf.position)
            estrade = self.market_order(esf.contract, -1 * esf.position)


class PairsTradingAlgo(BaseAlgo):
    def __init__(self, formation_period=("2021-10-05", "2022-10-05"), **kwargs):
        super(PairsTradingAlgo, self).__init__(**kwargs)

        # read in formation period data or generate it from historical data
        start, end = formation_period
        try:
            self.data = pd.read_csv("pairs-data.csv")
            print("Pairs data found in csv file.")
        except FileNotFoundError:
            print("Pairs data file not found. generating from historical data.")
            self.data = self._gen_formation_data(start, end)

    def _universe_selection(self):
        sp_data = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        )[0]
        tickers = sp_data.Symbol.to_list()
        return tickers

    def _form_pairs(self, num_pairs):
        sorted_pairs = []
        distances = {}
        for pair in self.ticker_pairs:
            distances[pair] = sum(
                (self.return_data[pair[0]] - self.return_data[pair[1]]) ** 2
            )
            sorted_pairs = sorted(distances, key=lambda x: distances[x])[:num_pairs]
        return sorted_pairs

    def _gen_formation_data(self, start_date, end_date):
        # get tickers from universe selection
        self.tickers = self._universe_selection()
        self.ticker_pairs = list(it.combinations(self.tickers, 2))
        self.sorted_pairs = None

        panel_data = pdr.DataReader(
            self.tickers, "yahoo", start=start_date, end=end_date
        )["Adj Close"]

        # get a price df
        price_data = pd.DataFrame(panel_data.to_dict())

        # change each column to cumulative returns to get a returns df
        df = price_data.copy(deep=True)
        for col in df:
            df[col] = df[col].pct_change().add(1).cumprod().sub(1)
        self.return_data = df.tail(252)

        # find 20 pairs with the minimum ssd and filter price data
        self.sorted_pairs = self._form_pairs(50)
        unique_tics = list(set([i for tup in self.sorted_pairs for i in tup]))

        # create log price data
        log_price_data = price_data[unique_tics].tail(252)
        for col in log_price_data:
            log_price_data[col] = np.log(log_price_data[col])

        # create a df to hold the formation period data we want to keep
        data = pd.DataFrame(
            columns=["pair", "hedge_ratio", "spread_mean", "spread_std"],
        )
        for pair in self.sorted_pairs:
            # tranform to log prices
            log_price_0 = log_price_data[pair[0]]
            log_price_1 = log_price_data[pair[1]]

            # regress log prices on eachother to get the hedge ratio
            model = sm.OLS(log_price_0, log_price_1).fit()
            hedge_ratio = model.params[0]
            spread = np.array(log_price_0 - hedge_ratio * log_price_1)
            mean = np.mean(spread)
            std = np.std(spread)

            # add data to dataframe
            data.loc[len(data.index)] = [pair, hedge_ratio, mean, std]

        # write pairs formation data out to a file adn return data
        data.to_csv("pairs-data.csv", index=False)
        return data

    def rebalance(self):
        # exit any open pairs traded positions
        positions = [p for p in self.ibconn.positions() if p.contract.secType == "STK"]

        # set a max portfolio allotment based on the number of positions
        max_allotment = min(
            self.portfolio_val / (len(self.data) * 2), self.max_position
        )

        # for each trading pair, calculate the current spread
        for index, row in self.data.iterrows():
            pair = literal_eval(row.pair)
            tic1, tic2 = pair

            # form contracts for the security pair
            sec1 = Stock(tic1, "SMART", "USD")
            sec2 = Stock(tic2, "SMART", "USD")
            self.ibconn.reqMarketDataType(4)
            contracts = self.ibconn.qualifyContracts(sec1, sec2)
            assert sec1 in contracts
            assert sec2 in contracts

            # price each security and calculate the spread and z-score
            [p1, p2] = self.ibconn.reqTickers(*contracts)
            if (p1.last and p2.last) == False:
                print(f"Can't find last price for one of {pair}. Skipping.")
                continue

            spread = np.log(p1.last) - row.hedge_ratio * np.log(p2.last)
            z_score = (spread - row.spread_mean) / row.spread_std

            filter = [p for p in positions if p.contract.symbol in pair]

            # set the allocation based on the first security
            allocation = np.floor(max_allotment / p1.last)

            # if the szcore is small and positions are open, liquidate them
            if abs(z_score) < 1 and len(filter) > 0:
                for stk in filter:
                    print(f"Zscore is {z_score} - closing {pair} positions...")
                    self.market_order(stk.contract, -1 * stk.position)
            # if the zscore exceeds 1 and no positions are open, long or short the spread
            elif z_score > 1 and len(filter) == 0:
                print(
                    f"Zscore is {z_score} - shorting {pair} spread with allocation of {allocation}"
                )
                self.market_order(sec1, -1 * allocation)
                self.market_order(sec2, np.floor(allocation * row.hedge_ratio))
            elif z_score < -1 and len(filter) == 0:
                print(
                    f"Zscore is {z_score} - long {pair} spread with allocation of {allocation}"
                )
                self.market_order(sec1, allocation)
                self.market_order(sec2, np.floor(-1 * allocation * row.hedge_ratio))
            else:
                print(f"Zscore is {z_score} - no action for {pair} spread...")