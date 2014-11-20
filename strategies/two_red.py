# A module for all built-in commands.
# vim: sw=4: et
LICENSE="""
Copyright (C) 2011  Michael Ihde

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""
import datetime
import os
import tables
import matplotlib.pyplot as plt
import matplotlib.mlab as mlab
import matplotlib.ticker as ticker
from utils.market import *
from indicators.simplevalue import SimpleValue
from strategy import Strategy
from utils.model import Order
from utils.date import ONE_DAY
from indicators.ema import EMA

class Trending(Strategy):
    DEF_LONG_DAYS = 200
    DEF_SHORT_DAYS = 15
    DEF_RSI_PERIOD = 14

    def __init__(self, start_date, end_date, initial_position, market, params, h5file=None):
        Strategy.__init__(self, start_date, end_date, initial_position, market, params, h5file)
        during = params['during']
        self.history = [1000.0 for x in xrange(during+1)]
        for symbol in initial_position.keys():
            if symbol == "$":
                continue
            self.addIndicator(symbol, "value", SimpleValue())
            try:
                short = params['short']
            except KeyError:
                short = Trending.DEF_SHORT_DAYS
            self.addIndicator(symbol, "short", EMA(short)) 
            try:
                long_ = params['long']
            except KeyError:
                long_ = Trending.DEF_LONG_DAYS
            self.addIndicator(symbol, "long", EMA(long_))
        try:
            backfill = params['backfill']
        except KeyError:
            backfill = long_
        d = start_date - (backfill * ONE_DAY)
        self.updateIndicators(d, start_date)
        self.win_point = params['win']
        self.loss_point = params['loss']
        
    def evaluate(self, date, position, market):
        orders = []
        # Based of indicators, create signals
        buyTriggers = []
        sellTriggers = []
        for symbol, qty in position.items():
            if symbol != '$':
                status = isTradingDay(date,symbol)
                if not status:
                    return  None
                self.updateIndicators(date)
                ticker = market[symbol]
                open_price = ticker[date].adjopen
                self.history.insert(0, open_price)
                diff = self.indicators[symbol]["short"].value - self.indicators[symbol]["long"].value
                if self.history == sorted(self.history,None,None,True) and diff > 0:
                    buyTriggers.append(symbol)
                if position[symbol].amount > 0 and ( (open_price-position[symbol].basis)/open_price > self.win_point or (position[symbol].basis-open_price)/open_price > self.loss_point):
                    sellTriggers.append(symbol)
                self.history.pop()
                print self.history
        
        for sellTrigger in sellTriggers:
            #print position[sellTrigger].amount
            if position[sellTrigger].amount > 0:
                orders.append(Order(Order.SELL, sellTrigger, "ALL", Order.MARKET_ON_CLOSE))

        # Evaluate all buy orders
        if len(buyTriggers) > 0:
            cash = position['$']
            #print cash
            cashamt = position['$'] / len(buyTriggers)
            for buyTrigger in buyTriggers:
                ticker = market[buyTrigger]
                close_price = ticker[date].adjclose
                if close_price != None:
                    estimated_shares = (int(cashamt / close_price)/100)*100
                    print "buy qty: %d" % estimated_shares
                    # Only issues orders that buy at least one share
                    #amount = estimated_shares*close_price
                    if estimated_shares >= 1:
                        orders.append(Order(Order.BUY, buyTrigger, "$%f" % cashamt, Order.MARKET_ON_CLOSE))
                
        return orders

CLAZZ = Trending
