#/usr/bin/env python
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
import imp
import time
import logging
import datetime
import numpy
import os
import sys
import tables
import math
import yaml
#from config import CONFIG
import config
from yahoo import Market
from utils.progress_bar import ProgressBar
from utils.model import *
from utils.market import *
from utils.date import ONE_DAY
from pycommando.commando import command
import matplotlib.pyplot as plt
import matplotlib.mlab as mlab
import matplotlib.ticker as ticker
import matplotlib.dates as dates
import portfolio
import report
import plots
import threading
import threadPool

def initialize_position(CONFIG, portfolio, date):
    p = CONFIG['portfolios'][portfolio]

    if not type(date) == datetime.datetime:
        date = datetime.datetime.strptime(date, "%Y-%m-%d")

    # Turn the initial cash value into shares based off the portfolio percentage
    position = {'$': 0.0}
    market = Market()
    for instrument, amt in p.items():
        instrument = instrument.strip()
        if type(amt) == str:
            amt = amt.strip()

        if instrument == "$":
            position[instrument] += float(amt)
        else:
            d = date
            quote = market[instrument][d]
            while quote == None:
                # Walk backwards looking for a day that had a close price, but not too far
                # because the given instrument may not exist at any time for the given
                # date or prior to it
                d = d - ONE_DAY
                if (date - d) > datetime.timedelta(days=7):
                    break
                quote = market[instrument][d]
            if quote == None:
                # This occurs it the instrument does not exist in the market
                # at the start of the simulation period
                position[instrument] = Position(0.0, 0.0)
                if type(amt) == str and amt.startswith('$'):
                    amt = float(amt[1:])
                    position['$'] += amt
                else:
                    print "Warning.  Non-cash value used for instrument that is not available at start of simulation period"
            else:
                price = quote.adjclose
                if type(amt) == str and amt.startswith('$'):
                    amt = float(amt[1:])
                    amt = math.floor(amt / price)
                position[instrument] = Position(float(amt), price)
    return position

def write_position(MARKET, table, position, date):
    for instrument, p in position.items():
        table.row['date'] = date.date().toordinal()
        table.row['date_str'] = str(date.date())
        table.row['symbol'] = instrument 
        if instrument == '$':
            table.row['amount'] = 0
            table.row['value'] = p
        else:
            table.row['amount'] = p.amount
            table.row['basis'] = p.basis
            quote = MARKET[instrument][date]
            #price = MARKET[instrument][date].adjclose
            if quote:
                price = MARKET[instrument][date].adjclose
                table.row['value'] = price
            else:
                table.row['value'] = 0.0
        table.row.append()

def write_performance(MARKET, table, position, date):
    value = 0.0
    for instrument, p in position.items():
        if instrument == '$':
            value += p
        else:
            quote = MARKET[instrument][date]
            if quote:
                price = MARKET[instrument][date].adjclose
                value += (price * p.amount)

    table.row['date'] = date.date().toordinal()
    table.row['date_str'] = str(date.date())
    table.row['value'] = value
    table.row.append()

def execute_orders(MARKET, table, position, date, orders):
    for order in orders:
        logging.debug("Executing order %s", order)
        if position.has_key(order.symbol):
            ticker = MARKET[order.symbol]
            if order.order == Order.SELL:
                if order.price_type == Order.MARKET_PRICE:
                    strike_price = ticker[date].adjopen
                elif order.price_type == Order.MARKET_ON_CLOSE:
                    strike_price = ticker[date].adjclose
                else:
                    raise StandardError, "Unsupport price type"

                qty = None
                if order.quantity == "ALL":
                    qty = position[order.symbol].amount
                else:
                    qty = order.quantity
                print "actually sell: %d" % qty
                if qty > position[order.symbol] or qty < 1:
                    logging.warn("Ignoring invalid order %s.  Invalid quantity", order)
                    continue
             
                price_paid = 0.0

                table.row['date'] = date.date().toordinal() 
                table.row['date_str'] = str(date.date())
                table.row['order_type'] = order.order
                table.row['symbol'] = order.symbol
                table.row['order'] = str(order)
                table.row['executed_quantity'] = qty
                table.row['executed_price'] = strike_price
                table.row['basis'] = position[order.symbol].basis 
                table.row.append()

                position[order.symbol].remove(qty, strike_price)
                position['$'] += (qty * strike_price)
                position['$'] -= 9.99 # TODO make trading cost configurable

            elif order.order == Order.BUY:
                if order.price_type == Order.MARKET_PRICE:
                    strike_price = ticker[date].adjopen
                elif order.price_type == Order.MARKET_ON_CLOSE:
                    strike_price = ticker[date].adjclose

                if type(order.quantity) == str and order.quantity[0] == "$":
                    qty = (int(float(order.quantity[1:]) / strike_price)/100)*100
                else:
                    qty = int(order.quantity)

                table.row['date'] = date.date().toordinal() 
                table.row['date_str'] = str(date.date())
                table.row['order_type'] = order.order
                table.row['symbol'] = order.symbol
                table.row['order'] = str(order)
                table.row['executed_quantity'] = qty
                table.row['executed_price'] = strike_price
                table.row['basis'] = 0.0
                table.row.append()

                position[order.symbol].add(qty, strike_price)
                position['$'] -= (qty * strike_price)
                position['$'] -= 9.99


def load_strategy(name):
    mydir = os.path.abspath(os.path.dirname(sys.argv[0]))
    strategydir = os.path.join(mydir, "strategies")
    sys.path.insert(0, strategydir)
    if name in sys.modules.keys():
        reload(sys.modules[name])
    else:
        __import__(name)
    #print sys.modules[name]
    clazz = getattr(sys.modules[name], "CLAZZ")
    sys.path.pop(0)

    return clazz


@command("analyze")
def analyze(strategy_name, portfolio, strategy_params="{}"):
    """Using a given strategy and portfolio, make a trading decision"""
    now = datetime.datetime.today()
    position = initialize_position(portfolio, now)

    # Initialize the strategy
    params = yaml.load(strategy_params)
    strategy_clazz = load_strategy(strategy_name)
    strategy = strategy_clazz(now, now, position, MARKET, params)
    
    orders = strategy.evaluate(now, position, MARKET)

    for order in orders:
        print order

@command("simulate")
def simulate(MARKET, CONFIG, strategy_name, portfolio, start_date, end_date, output="~/.quant/simulation.h5", strategy_params="{}"):
    """A simple simulator that simulates a strategy that only makes
    decisions at closing.  Only BUY and SELL orders are supported.  Orders
    are only good for the next day.

    A price type of MARKET is executed at the open price the next day.

    A price type of MARKET_ON_CLOSE is executed at the close price the next day.

    A price type of LIMIT will be executed at the LIMIT price the next day if LIMIT
    is between the low and high prices of the day.

    A price type of STOP will be executed at the STOP price the next day if STOP
    is between the low and high prices of the day.

    A price type of STOP_LIMIT will be executed at the LIMIT price the next day if STOP
    is between the low and high prices of the day.
    """

    outputFile = openOutputFile(output)
    # Get some of the tables from the output file
    order_tbl = outputFile.getNode("/Orders")
    postion_tbl = outputFile.getNode("/Position")
    performance_tbl = outputFile.getNode("/Performance")
        
    start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
    # Start the simulation at closing of the previous trading day
    print start_date 
    now = getPrevTradingDay(MARKET, start_date)
    try:
        position = initialize_position(CONFIG, portfolio, now)
        for instrument, p in position.items():
            if instrument != '$':
                quote = MARKET[instrument][now]
                if quote == None:
                    return
        # Pre-cache some info to make the simulation faster
        '''
        ticker = MARKET["399001.sz"].updateHistory(start_date, end_date)
        for symbol in position.keys():
            if symbol != '$':
                MARKET[symbol].updateHistory(start=start_date, end=end_date)
        '''
        days = (end_date - start_date).days
        
        # Initialize the strategy
        params = yaml.load(strategy_params)
        imp.acquire_lock()
        strategy_clazz = load_strategy(strategy_name)
        imp.release_lock()
        print 'jinxiaoyi'
        strategy = strategy_clazz(start_date, end_date, position, MARKET, params, outputFile)
        p = ProgressBar(maxValue=days, totalWidth=80)
        print "Starting Simulation %s" % portfolio
        # Write the initial position to the database
        write_position(MARKET,postion_tbl, position, now)
        write_performance(MARKET,performance_tbl, position, now)
        while now <= end_date:
            #print now
            # Remember 'now' is after closing, so the strategy
            # can use any information from 'now' or earlier
            #orders = strategy.evaluate(now, position, MARKET)
            # Go to the next day to evalute the orders          
            while 1:
                orders = strategy.evaluate(now, position, MARKET)
                if orders == 'outdate':
                    outputFile.close()
                    return
                if orders == None:
                    now += ONE_DAY
                    p.performWork(1)
                else:
                    break
            # Execute orders
            execute_orders(MARKET, order_tbl, position, now, orders)
            write_position(MARKET, postion_tbl, position, now)
            write_performance(MARKET, performance_tbl, position, now)
            now += ONE_DAY
            # Flush the data to disk
            outputFile.flush()
            p.performWork(1)
            #print p, '\r'
            
        p.updateAmount(p.max)
        #print p, '\r',
        #print '\r\n' # End the progress bar here before calling finalize
        orders = strategy.finalize()
    finally:
        outputFile.close()
        
def createHighLow(index):
    MARKET = Market()
    CONFIG = config._Config(index)
    portfolio.delete(CONFIG, index)
    portfolio.create(CONFIG, index, 10000, '{%s: $0}' % index)
    file_name = './quant/highLow/peak%s.h5' % index.split('.')[0]
    simulate(MARKET, CONFIG, 'highlow', index, '2014-01-06', '2014-10-21', file_name, '{short: 18, long: 47, during: 2, win: 0.07, loss: 0.03}')
    return index
    
if __name__ == '__main__':
    print datetime.date.today()
    #logging.basicConfig(level=logging.ERROR)
    '''
    china = Market()
    china.updateHistory()
    '''
    #china = Market()
    #symbols = china.cache.symbols()
    #createHighLow('002391.sz')
    #file_name = './quant/highLow/peak002391.h5'
    #plots.plot_indicators('002391.sz', 'all', file_name)
    
    symbols = ['002391.sz', '000002.sz', '000004.sz', '600475.ss', '000584.sz', '600720.ss', '002020.sz', '300039.sz', '600468.ss', '300096.sz']
    wm = threadPool.WorkerManager(4)
    for index in symbols:
        wm.add_job(createHighLow, index)
    wm.wait_for_complete()
    
    
    '''
    threads = []
    count = 0
    china = Market()
    #createHighLow('000673.sz')
    #china.fetchHistory()

    symbols = china.cache.symbols()
    for index in symbols:
        createHighLow(index)
    '''
    '''
        count += 1
        t = threading.Thread(target=createHighLow, args=(index,))
        threads.append(t)
        if count/10 == 0:
            for t in threads:    
                t.start()
            for t in threads:
                t.join()
            threads = []
    '''
    '''
    for i in range(30,50):
        portfolio.delete('300172.sz')
        portfolio.create('300172.sz', 10000, '{300172.sz: $0}')
        file_name = './quant/expma%d.h5' % i
        simulate( 'trending_with_ema', '300172.sz', '2014-01-01', '2014-07-01', file_name, '{long: %d, short: 18}' % i)
    '''
    '''
    for i in range(30,50):
        file_name = './quant/expma%d.h5' % i
        report1 = report.calculate_performance(file_name)
        print "EMA: %d" % i
        print "Starting Value: $%(starting_value)0.2f" % report1
        print "Ending Value: $%(ending_value)0.2f" % report1
        print "Return: $%(equity_return)0.2f (%(equity_percent)3.2f%%)" % report1
    '''
    '''
    for i in range(30,50):
        file_name = './quant/expma%d.h5' % i
        plots.plot_indicators('300172.sz', 'all', file_name)
    '''
    
    #index = '300206.sz'
    '''
    threads = []
    indexs = ['000001.sz', '000002.sz', '000004.sz', '000005.sz', '000006.sz', '000008.sz', '000009.sz', '000010.sz', '000011.sz', '000012.sz', '000014.sz', '000016.sz', '000017.sz', '000018.sz', '000019.sz', '000020.sz', '000021.sz', '000022.sz', '000023.sz', '000024.sz', '000025.sz', '000026.sz', '000027.sz', '000028.sz', '000029.sz', '000030.sz', '000031.sz', '000032.sz', '000033.sz', '000034.sz', '000035.sz', '000036.sz', '000037.sz', '000038.sz', '000039.sz', '000040.sz']
    for index in indexs:
        portfolio.delete(index)
        portfolio.create(index, 10000, '{%s: $0}' % index)
        file_name = './quant/two_red%s.h5' % index.split('.')[0]
        simulate('two_red', index, '2014-01-01', '2014-09-30', file_name, '{short: 18, long: 47, during: 2, win: 0.07, loss: 0.03}')    
    '''
    '''
    indexs = ['000001.sz', '000002.sz', '000004.sz', '000005.sz', '000006.sz', '000008.sz', '000009.sz', '000010.sz', '000011.sz', '000012.sz', '000014.sz', '000016.sz', '000017.sz']
    for index in indexs:
        print "index: %s" % index
        file_name = './quant/two_red%s.h5' % index.split('.')[0]
        report1 = report.calculate_performance(file_name)
        print "Starting Value: $%(starting_value)0.2f" % report1
        print "Ending Value: $%(ending_value)0.2f" % report1
        print "Return: $%(equity_return)0.2f (%(equity_percent)3.2f%%)" % report1
    '''
    #plots.plot('./quant/two_red.h5')
    #plots.plot_indicators(index, 'all', './quant/two_red.h5')
    #plots.show()
    
    #report.report_performance('./quant/trending.h5')
    #plots.plot_indicators('300172.sz', 'all', './quant/expma47.h5')
    #plots.plot('./quant/expma.h5')
    #plots.show()
    '''
    index = "300065.sz"
    portfolio.delete(index)
    portfolio.create(index, 10000, '{%s: $0}' % index)
    file_name = './quant/peak%s.h5' % index.split('.')[0]
    simulate('highlow', index, '2013-01-05', '2014-09-30', file_name, '{short: 18, long: 47, during: 2, win: 0.07, loss: 0.03}')
    #report.report_performance(file_name)
    plots.plot_indicators(index, 'all', file_name)
    #plots.plot(file_name)
    plots.show()
    '''
    '''
    index = "600030.ss"
    portfolio.delete(index)
    portfolio.create(index, 10000, '{%s: $0}' % index)
    file_name = './quant/ma%s.h5' % index.split('.')[0]
    simulate('averageSystem', index, '2014-01-05', '2014-09-30', file_name, '{short: 18, long: 47, period: 60, win: 0.07, loss: 0.03}')
    report.report_performance(file_name)
    plots.plot_indicators(index, 'all', file_name)
    plots.plot(file_name)
    plots.show()
    '''
    '''
    index = "600030.ss"
    file_name = './quant/peak%s.h5' % index.split('.')[0]
    plots.plot_indicators(index, 'all', file_name)
    plots.show()
    inputFile = tables.openFile(os.path.expanduser(file_name), "r")
    print inputFile.list_nodes("/Indicators/" + index, classname="Table")
    try:
        for tbl in inputFile.iterNodes("/Indicators/" + index, classname="Table"):
            if tbl.name == 'peak':
                x_data = tbl.col('date')
                y_data = tbl.col('value')
                z_data = tbl.col('flag')
                print x_data
                print y_data
                print z_data
    finally:
        inputFile.close()
    print min(y_data)
    print max(y_data)
    '''
        

        
