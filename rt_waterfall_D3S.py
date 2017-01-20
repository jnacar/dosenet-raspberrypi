from auxiliaries import set_verbosity
from plotter_D3S import Plotter_D3S

import numpy as np
import matplotlib.pyplot as plt

class Rt_Waterfall_D3S(object):
    """
    Class for running the D3S in real-time waterfall mode
    """
    
    def __init__(self, 
                 manager=None, 
                 verbosity=1,
                 logfile=None,
                ):
        
        self.v = verbosity
        if manager and logfile is None:
            set_verbosity(self, logfile=manager.logfile)
        else:
            set_verbosity(self, logfile=logfile)
            
        self.manager = manager
        
        self.interval = manager.interval
        
        self.queuelength = None
        self.image = None
        
        self.plotter = Plotter_D3S(
                interval=self.interval, 
                rt_waterfall=self)
    
        self.plotter.main()
    
    def get_data(self, spectra, queue1, queue2):
        queue1.append(spectra)
        queue2.append(spectra)
        return queue1, queue2
   

    def fix_array(self, array):
        """
        Used to format arrays for the waterfall plot.Called inside make_image.
        """
        new_array = np.zeros((256))
        i = 0
        while i < 256:
            new_array[i] = array[i]
            i += 1
        return new_array
     
    def reset_queue(self, queue1, queue2): 
        for i in queue2: 
            queue1.append(i)
        return queue1, queue2
      
    def make_image(self, queue1, queue2):
        """
        Prepares an array for the waterfall plot
        """
        length = len(queue1)

        self.image = np.zeros((length, 256),dtype=float)
        i = 0
        while i < length:
            self.image[i] = self.fix_array(queue1.popleft())
            i += 1
        queue1, queue2 = self.reset_queue(queue1, queue2)
        return queue1, queue2
      
    def waterfall_graph(self, spectra, queue1, queue2):
        """
        Plots a waterfall graph of all the spectra.
        """
        queue1, queue2 = self.get_data(spectra, queue1, queue2)
        self.queue_length = len(queue2)
        queue1, queue2 = self.make_image(queue1, queue2)

        return queue1, queue2
      
    def update(self, spectra, queue1, queue2):
        queue1, queue2 = self.waterfall_graph(spectra, queue1, queue2)
        return queue1, queue2
