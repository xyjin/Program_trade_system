import time
import Queue, threading, sys   
from threading import Thread    
# working thread   
class Worker(Thread):   
   worker_count = 0   
   def __init__( self, workQueue, resultQueue, timeout = 0, **kwds):   
       Thread.__init__( self, **kwds )   
       self.id = Worker.worker_count   
       Worker.worker_count += 1   
       self.setDaemon( True )   
       self.workQueue = workQueue   
       self.resultQueue = resultQueue   
       self.timeout = timeout   
       self.start( )   
   def run( self ):   
       ''' the get-some-work, do-some-work main loop of worker threads '''   
       while True:   
           try:   
               callable, args, kwds = self.workQueue.get(timeout=self.timeout)   
               res = callable(*args, **kwds)   
               #print "worker[%2d]: %s\n" % (self.id, str(res) )   
               #self.resultQueue.put( res )   
           except Queue.Empty:   
               break   
           except :   
               print 'worker[%2d]' % self.id, sys.exc_info()   
                  
class WorkerManager:   
   def __init__( self, num_of_workers=10, timeout = 1):   
       self.workQueue = Queue.Queue()   
       self.resultQueue = Queue.Queue()   
       self.workers = []   
       self.timeout = timeout   
       self._recruitThreads( num_of_workers )   
   def _recruitThreads( self, num_of_workers ):   
       for i in range( num_of_workers ):   
           worker = Worker( self.workQueue, self.resultQueue, self.timeout )   
           self.workers.append(worker)   
   def wait_for_complete( self): 
       import random
       # ...then, wait for each of them to terminate:   
       while len(self.workers):
           time.sleep(random.uniform(1,5)/10)
           worker = self.workers.pop()   
           worker.join( )   
           if worker.isAlive() and not self.workQueue.empty():   
               self.workers.append( worker )   
       print "All jobs are are completed."   
       
   def add_job( self, callable, *args, **kwds ):   
       self.workQueue.put( (callable, args, kwds) )   
       
   def get_result( self, *args, **kwds ):   
       return self.resultQueue.get( *args, **kwds )
      
def test_job(id, sleep = 0.001 ):
   import random
   try:   
       #urllib.urlopen('[url]https://www.baidu.com/[/url]').read()
      #sleep(random.uniform(10, 20))
      print id
   except:   
       print '[%4d]' % id, sys.exc_info()[:2]   
   return id   
def test():   
   import socket   
   socket.setdefaulttimeout(10)   
   print 'start testing'   
   wm = WorkerManager(10)   
   for i in range(500):   
       wm.add_job( test_job, i, i*0.001 )   
   wm.wait_for_complete()   
   print 'end testing'

if __name__ == '__main__':
   test()