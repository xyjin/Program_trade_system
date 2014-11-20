#!/usr/bin/env python
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
from yahoo import Market
from utils.date import ONE_DAY
import datetime

#MARKET = Market()
def isTradingDay(MARKET, date, sym='000001.ss'):
    if date.weekday() in (0,1,2,3,4):
        # Consider any day the Dow was active as a trading day
        #ticker = MARKET["000001.ss"]
       ticker = MARKET[sym]
       if (ticker != None):
            quote = ticker[date]
            if quote=='outdate':
                return 'outdate'
            if quote==None:
                return False
            if quote.adjclose != None:
                return True
    return False
    
def getPrevTradingDay(MARKET,  date, sym='000001.ss'):
    prev_trading_day = date - ONE_DAY
    while isTradingDay(MARKET, prev_trading_day, sym) == False:
        prev_trading_day = prev_trading_day - ONE_DAY
        if (date - prev_trading_day)> datetime.timedelta(days=5):
            break
    return prev_trading_day

def getNextTradingDay(MARKET, date, sym='000001.ss'):
    next_trading_day = date + ONE_DAY
    while isTradingDay(MARKET, next_trading_day, sym) == False:
        next_trading_day = next_trading_day - ONE_DAY
    return next_trading_day
'''
def isTradingDay(date):
    if date.weekday() in (0,1,2,3,4):
        # Consider any day the Dow was active as a trading day
        ticker = MARKET["000001.ss"]
       # ticker = MARKET[sym]
        if (ticker != None):
            quote = ticker[date]
            if quote==None:
                return False
            if quote.adjclose != None:
                return True
    return False


def getPrevTradingDay(date):
    prev_trading_day = date - ONE_DAY
    while isTradingDay(prev_trading_day) == False:
        prev_trading_day = prev_trading_day - ONE_DAY
    return prev_trading_day

def getNextTradingDay(date):
    next_trading_day = date + ONE_DAY
    while isTradingDay(next_trading_day) == False:
        next_trading_day = next_trading_day - ONE_DAY
    return next_trading_day
'''
