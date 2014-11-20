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
from indicators.peaktrough import PeakTrough
from strategy import Strategy
from utils.model import Order
from utils.date import ONE_DAY
from indicators.ema import EMA

DURING_SLOT=3
def calcMax(left, right):
    if left > right:
        return left,1
    else:
        return right,0
def calcMin(left, right):
    if left > right:
        return right,1
    else:
        return left,0
        
class HighLow(Strategy):
    DEF_LONG_DAYS = 200
    DEF_SHORT_DAYS = 15
    DEF_RSI_PERIOD = 14

    def __init__(self, start_date, end_date, initial_position, market, params, h5file=None):
        Strategy.__init__(self, start_date, end_date, initial_position, market, params, h5file)
        for symbol in initial_position.keys():
            if symbol == "$":
                continue
            self.addIndicator(symbol, "value", SimpleValue())
            self.addSpecificIndicator(symbol, "peak", PeakTrough())
            date = getPrevTradingDay(market, start_date, symbol)
            #date = getNextTradingDay(start_date, symbol)
            self.peakDate = date
            self.troughDate = date
            ticker = market[symbol]
            if ticker[date] == None:
                self.max_value = 0
                self.min_value = 1000
            else:
                self.max_value = ticker[date].adjhigh
                self.min_value = ticker[date].adjlow
            self.updateSpecificIndicator(symbol, 'peak', start_date, (self.max_value, 1))
        self.updateIndicators(start_date)
        self.win_point = params['win']
        self.loss_point = params['loss']
        self.low_to_high = 0
        self.high_to_low = 0
        self.upTrend = 0
        self.downTrend = 0
        
    def evaluate(self, date, position, market):
        orders = []
        buyTriggers = []
        sellTriggers = []
        # Based of indicators, create signals
        for symbol, qty in position.items():
            if symbol != '$':
                status = isTradingDay(market, date,symbol)
                if status == 'outdate':
                    return 'outdate'
                if not status:
                    return  None
                self.updateIndicators(date)
                pre_date = getPrevTradingDay(market, date, symbol)
                ticker = market[symbol]
                if ticker[date] == None:
                    return orders
                high_price = ticker[date].adjhigh
                pre_high_price = ticker[pre_date].adjhigh
                low_price = ticker[date].adjlow
                pre_low_price = ticker[pre_date].adjlow
                
                if high_price >= pre_high_price:
                    flag=1  #up
                    self.upTrend += 1
                    self.max_value,bigger = calcMax(high_price, self.max_value)
                    if bigger == 1:
                        self.peakDate = date
                    if bigger == 1 and self.low_to_high == 1:
                        self.downTrend = 0
                else:
                    flag=0
                    self.downTrend += 1
                    self.min_value,less = calcMin(low_price, self.min_value)
                    if less == 1:
                        self.troughDate = date
                    if less == 1 and self.high_to_low == 1:
                        self.upTrend = 0
                if (flag==0 and self.upTrend>=DURING_SLOT and self.downTrend>=DURING_SLOT):
                    self.updateSpecificIndicator(symbol, 'peak', self.peakDate, (self.max_value, 1))
                    self.upTrend = 0
                    self.min_value = low_price
                    self.troughDate = date
                    self.low_to_high = 0
                    self.high_to_low = 1
                if (flag==1 and self.upTrend >= DURING_SLOT and self.downTrend >= DURING_SLOT):
                    self.updateSpecificIndicator(symbol, 'peak', self.troughDate, (self.min_value, 0))
                    self.downTrend = 0
                    self.max_value = high_price
                    self.peakDate = date
                    self.high_to_low = 0
                    self.low_to_high = 1

        # Evaluate all buy/sell orders
        for sellTrigger in sellTriggers:
            if position[sellTrigger].amount > 0:
                orders.append(Order(Order.SELL, sellTrigger, "ALL", Order.MARKET_ON_CLOSE))
        if len(buyTriggers) > 0:
            cash = position['$']
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

CLAZZ = HighLow