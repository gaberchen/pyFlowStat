'''
PointProbe.py

Collection of tools/functions to load and/or get spectral analysis of time series extracted from
a turbulent flow field.

functions included:
    readOfRuntime(probeLoc,ofFile,rtnType='numpy')
    genPtStat(probeName,probeLoc,tserie,Userie)
'''


#===========================================================================#
# load modules
#===========================================================================#
#standard modules
import sys
import re
import os
import csv
import collections

#scientific modules
import numpy as np
import scipy as sp
from scipy import signal
from scipy.optimize import curve_fit
# special modules

#from pyFlowStat.TurbulenceTools import TurbulenceTools as tt
import pyFlowStat.TurbulenceTools as tt
import pyFlowStat.Surface as Surface

class PointProbe(object):
    '''
    PointProbe Class
    
    A class to handle velocity time serie from a point.
    '''
    
    def __init__(self):
        self.probeLoc=[]
        self.probeTimes=[]
        self.probeVar=[]
        return

    #===========================================================================#
    # functions
    #===========================================================================#
    def t(self):
        return self.data['t']
    def Ux(self):
        return self.data['U'][:,0]
    def Uy(self):
        return self.data['U'][:,1]
    def Uz(self):
        return self.data['U'][:,2]
    def Umag(self):
        return self.data['Umag']
    def ux(self):
        return self.data['u'][:,0]
    def uy(self):
        return self.data['u'][:,1]
    def uz(self):
        return self.data['u'][:,2]
    def Umean(self):
        return np.mean(self.data['Umag'])
     
    def uu_bar(self):
        return np.mean(pow(signal.detrend(self.ux()),2))
    def vv_bar(self):
        return np.mean(pow(signal.detrend(self.uy()),2))
    def ww_bar(self):
        return np.mean(pow(signal.detrend(self.uz()),2))
    def uv_bar(self):
        return np.mean(signal.detrend(self.ux())*signal.detrend(self.uy()))
    def uw_bar(self):
        return np.mean(signal.detrend(self.ux())*signal.detrend(self.uz()))
    def vw_bar(self):
        return np.mean(signal.detrend(self.uy())*signal.detrend(self.uz()))
    def TKE_bar(self):
        return 0.5*(self.uu_bar()+self.vv_bar()+self.ww_bar())
    
    def __iter__(self): 
        ''' 
        '''
        return self.data.itervalues()

    def __getitem__(self, key):
        '''      
        '''
        return self.data[key]
       
    def __setitem__(self, key, item):
        '''
        '''
        self.data[key] = item
        
    def readFromOpenFoam(self,probeLoc,filepath):
        '''
        Read runtime post-processing probe generated by the OpenFOAM.
        It updates member variables probeVar and probeTimes, then creates a data
        dictionnary. See member function createDataDict for more information about
        data dict.
        
        Arguments:
            * probeLoc: [numpy.array or python list. shape=()] Coordinate of probe (must be included in ofFile)
            * filepath: [string] Path to OpenFOAM probe file

        Returns:
            None
        '''
        probeTimes = []
        probeVar = []
        # read file 
        crs = open(filepath, 'r')
        lineno = 0
        for line in crs:
            # This regex finds all numbers in a given string.
            # It can find floats and integers writen in normal mode (10000) or with power of 10 (10e3).
            match = re.findall('[-+]?\d*\.?\d+e*[-+]?\d*', line)
            #print(match)
            if lineno==0:
                allXs = match
            if lineno==1:
                allYs = match
            if lineno==2:
                allZs = match
                ptFound = False
                for i in range(len(allXs)):
                    if (float(allXs[i])==probeLoc[0] and float(allYs[i])==probeLoc[1] and float(allZs[i])==probeLoc[2]):
                        ptPos = i
                        ptFound = True
                if ptFound==True:
                    #print('Probe found!')
                    pass
                else:
                    print('Probe not found!')
                    break          
            if lineno>3 and len(match)>0:
                if lineno==4:
                    varSize = int((len(match)-1)/(len(allXs)))  #check if probe var is scalar, vec or tensor
                    srtindex = 1+ptPos*varSize
                    endindex = srtindex+varSize
                probeTimes.append(float(match[0]))
                #probeTimes.append(float(match[0]))
                probeVar.append([float(var) for var in match[srtindex:endindex]])
            else:
                pass
            lineno = lineno+1
        crs.close()
        self.probeLoc = probeLoc
        self.probeTimes = np.array(probeTimes)
        self.probeVar = np.array(probeVar)
        self.createDataDict()
        
    def readFromLDA(self,probeLoc,filepath):
        '''
        Read LDA file.
        It updates member variables probeVar and probeTimes, then creates a data
        dictionnary. See member function createDataDict for more information about
        data dict.
        
        Arguments:
            probeLoc: [numpy.array or python list. shape=(3)] Coordinate of probe (must be included in ofFile)
            filepath: [string] Path to OpenFOAM probe file
     
        Returns:
            None
        '''
        probeVar = []
        probeTimes = []
        
        crs = open(filepath, 'r')
        lineno = 0
        for line in crs:
            if lineno>=5:
                data=line.split()
                probeTimes.append(float(data[0])/1000.0)
                probeVar.append([float(data[2]),0,0])
            lineno = lineno+1
        crs.close()
        self.probeLoc=probeLoc
        self.probeVar=np.array(probeVar)
        self.probeTimes=np.array(probeTimes)
        self.createDataDict()
        
    def appendData(self,U):
        '''
        Append velocity field U to self['U'] and extend self['t'] accordingly.
        Low level method: The following known issues are not checked:
            * gap: gap between U and self['U']
            * overlap: overlap between U and self['U']. Use method "cutData" to solve such issues
            * fequency missmatch: sampling frequency between U and self['U'] must be identical
            * location: append datas should (must?) come from the same probe location
         
        Arguments:
            * U: [np.array. shape=(N,3)] instentenous velocity fields Ux, Uy and Uz
        '''
        # append U        
        self.probeVar = np.vstack((self.probeVar,U))
        # complet self['t'] according total length of self['U']
        t0 = self.probeTimes[0]
        frq = self.data['frq']
        iterable = (t0+(1/frq)*i for i in range(self.probeVar.shape[0]))
        self.probeTimes = np.fromiter(iterable, np.float)
        self.createDataDict()

    
    def appendProbe(self,probe):
        '''        
        Append "probe" (PointProbe object) to current data.
        The following known issues are not checked:
            * gap: gap between U and self['U']
            * overlap: overlap between U and self['U']. Use method "cutData" to solve such issues
            * fequency missmatch: sampling frequency between U and self['U'] must be identical
            * location: append datas should (must?) come from the same probe location
            
        Arguments:
            * probe: [PointProbe object] PointProbe object to append
        '''
        self.appendData(probe['U'])
        
    
    def cutData(self,indices):
        '''
        Cut data according indices.
        
        Arguments:
            * indices: [np.array of python list] list of int
        
        Example (assume pt as a PointProbe object):
            >>> pt['U'].shape
            [10000,3]
            >>>pt.cutData([3,4,5,6,7]) # data from index 3 to 7
            >>>pt.cutData(np.arange(10,1000))  # data from index 10 to 1000
            >>>pt.cutData(np.arange(10,1000,5))  # data from index 10 to 1000 but only every 5 indices
        '''
        self.probeVar=self.probeVar[np.array(indices),:]
        self.probeTimes=self.probeTimes[np.array(indices),:]
        self.createDataDict()
        
    def createDataDict(self):
        '''
        Creates the "data" dictionnary from member variable probeLoc, probeTimes and probeVar
        
        Member variable data (python ditionary) is created. It holds all the series
        which can be generate with the t and U. To add a new entry to data,
        type somthing like:
        pt.PointProbe()
        pt.readFromLDA(point,file)
        pt['myNewKey'] = myWiredNewEntry 
        
        By default, the following keys are included in data:
            pos:  [numpy.array. shape=(3)] Probe location
            frq:  [float] Sample frequence
            U:    [numpy.array. shape=(N,3)] Velocity U
            t:    [numpy.array. shape=(N)]   Time t
            u:    [numpy.array. shape=(N,3)] Velocity fluctuation u
            Umag: [numpy.array. shape=(N)]   Velocity magnitute Umag
            umag: [numpy.array. shape=(N)]   Fluctuating velocity magnitute umag   
            Uoo:  [numpy.array. shape=(N,3)] Mean velocity with infinit window size
        '''
        
        self.data = dict()
        self.data['pos'] = self.probeLoc
        # velocity and time
        self.data['U'] = self.probeVar
        self.data['t'] = self.probeTimes
        
        # timestep, sample frequence
        self.data['dt']=self.data['t'][1]-self.data['t'][0]
        self.data['frq'] = 1/self.data['dt']
        
        #Umag
        Umag = np.zeros(self.data['U'].shape[0])
        for i in range(self.data['U'].shape[0]):
            a=self.data['U'][i,:]
            nrm2, = sp.linalg.get_blas_funcs(('nrm2',), (a,))
            Umag[i] = nrm2(a)
            #Umag[i] = np.linalg.norm(self.data['U'][i,:])
        self.data['Umag']=Umag
        #mean
        Uoo = np.zeros((self.data['U'].shape))
        Uoo[:,0] = np.mean(self.data['U'][:,0])
        Uoo[:,1] = np.mean(self.data['U'][:,1])
        Uoo[:,2] = np.mean(self.data['U'][:,2])
        self.data['Uoo'] = Uoo
        # fluctuation
        self.data['u'] = self.data['U']-self.data['Uoo']
        #umag
        umag = np.zeros(self.data['u'].shape[0])
        for i in range(self.data['u'].shape[0]):
            a=self.data['u'][i,:]
            nrm2, = sp.linalg.get_blas_funcs(('nrm2',), (a,))
            umag[i] = nrm2(a)
            #umag[i] = np.linalg.norm(self.data['u'][i,:])
        

    def generateStatistics(self,doDetrend=True):
        '''
        Generates statistics and populates member variable data.
        
        Arguments:
            doDetrend: detrend data bevor sigbal processing
            
        Populates the "data" python dict with with the following keys:
            rii:    [numpy.array of shape=(?)] Auto-correlation coefficent rii. For i=1,2,3 
            taurii: [numpy.array of shape=(?)] Time lags for rii. For i=1,2,3
            Rii:    [numpy.array of shape=(?)] Auto-correlation Rii. For i=1,2,3 
            tauRii: [numpy.array of shape=(?)] Time lags for Rii. For i=1,2,3
            
            uifrq:  [numpy.array of shape=(?)] u1 in frequency domain. For i=1,2,3
            uiamp:  [numpy.array of shape=(?)] amplitude of u1 in frequency domain. For i=1,2,3
            Seiifrq:[numpy.array of shape=(?)] Frequencies for energy spectrum Seii. For i=1,2,3
            Seii:   [numpy.array of shape=(?)] Energy spectrum Seii derived from Rii. For i=1,2,3
        '''   
        # auto correlation corefficient of u
        if doDetrend:
            ux=signal.detrend(self.ux());
            uy=signal.detrend(self.uy());
            uz=signal.detrend(self.uz());
        else:
            ux=self.ux();
            uy=self.uy();
            uz=self.uz();
        #ux=ux[-samples:-1]
        #uy=uy[-samples:-1]
        #uz=uz[-samples:-1]
        self.data['r11'],self.data['taur11'] = tt.xcorr_fft(ux, maxlags=None, norm='coeff')
        self.data['r22'],self.data['taur22'] = tt.xcorr_fft(uy, maxlags=None, norm='coeff')
        self.data['r33'],self.data['taur33'] = tt.xcorr_fft(uz, maxlags=None, norm='coeff')
        # auto correlation of u
        self.data['R11'],self.data['tauR11'] = tt.xcorr_fft(ux, maxlags=None, norm='none')
        self.data['R22'],self.data['tauR22'] = tt.xcorr_fft(uy, maxlags=None, norm='none')
        self.data['R33'],self.data['tauR33'] = tt.xcorr_fft(uz, maxlags=None, norm='none')
        
        
        #u in frequency domain
        self.data['u1frq'],self.data['u1amp'] = tt.dofft(sig=ux,samplefrq=self.data['frq'])
        self.data['u2frq'],self.data['u2amp'] = tt.dofft(sig=uy,samplefrq=self.data['frq'])
        self.data['u3frq'],self.data['u3amp'] = tt.dofft(sig=uz,samplefrq=self.data['frq'])
        #Time energy sectrum Se11 (mean: Rii in frequency domain...)
        self.data['Se11frq'],self.data['Se11'] = tt.dofft(sig=self.data['R11'],samplefrq=self.data['frq'])
        self.data['Se22frq'],self.data['Se22'] = tt.dofft(sig=self.data['R22'],samplefrq=self.data['frq'])
        self.data['Se33frq'],self.data['Se33'] = tt.dofft(sig=self.data['R33'],samplefrq=self.data['frq'])
        
    def generateDiagnosticStatistics(self):
        self.data['Uoo_c']=np.zeros(self.data['U'].shape)
        
        self.data['Uoo_c'][0,0]=self.data['U'][0,0]
        self.data['Uoo_c'][0,1]=self.data['U'][0,1]
        self.data['Uoo_c'][0,2]=self.data['U'][0,2]
        
        for i in range(1,len(self.probeTimes)):
            self.data['Uoo_c'][i,0]=self.data['Uoo_c'][i-1,0]+self.data['U'][i,0]
            self.data['Uoo_c'][i,1]=self.data['Uoo_c'][i-1,1]+self.data['U'][i,1]
            self.data['Uoo_c'][i,2]=self.data['Uoo_c'][i-1,2]+self.data['U'][i,2]
            
        for i in range(1,len(self.probeTimes)):
            self.data['Uoo_c'][i,0]=self.data['Uoo_c'][i,0]/(i+1)
            self.data['Uoo_c'][i,1]=self.data['Uoo_c'][i,1]/(i+1)
            self.data['Uoo_c'][i,2]=self.data['Uoo_c'][i,2]/(i+1)
        
    def lengthScale(self):
        '''
        Compute turbulent length scale (in time) in all three directions.
        
        Arguments:
            * none
        
        Returns:
            * none
        
        Member modifications:
            * self.data['Tii']: [np.float()]
            * self.data['Lii']: [np.float()]
        '''
        def func_exp(x, a):
            np.seterr('ignore')
            res = np.exp(-x/a)

            #print res
            return res
            
        def func_gauss(x, a):
            np.seterr('ignore')
            res = np.exp(-(x*x)/(a*a))

            #print res
            return res    
            
        corr_keys=['taur11','taur22','taur33','r11','r22','r33']
        if len(set(corr_keys) & set(self.data.keys()))!=len(corr_keys):
            self.generateStatistics()
            print "Generating Missing Statistics"
            
        xdata=self.data['taur11']
        ydata=self.data['r11']

        try:
            popt, pcov = curve_fit(func_exp,xdata,ydata)
            #self.data['Txx']=abs(popt[0])*np.sqrt(np.pi)*0.5*self.data['dt']
            self.data['Txx']=popt[0]*self.data['dt']
            self.data['Lxx']=self.data['Txx']*self.Umean()
        except RuntimeError:
            print("Error - curve_fit failed")
            self.data['Txx']=0
            self.data['Lxx']=0
        
        xdata=self.data['taur22']
        ydata=self.data['r22']
        try:
            popt, pcov = curve_fit(func_exp,xdata,ydata)
            self.data['Tyy']=popt[0]*self.data['dt']
            self.data['Lyy']=self.data['Tyy']*self.Umean()
        except RuntimeError:
            print("Error - curve_fit failed")
            self.data['Tyy']=0
            self.data['Lyy']=0
        
        xdata=self.data['taur33']
        ydata=self.data['r33']
        try:
            popt, pcov = curve_fit(func_exp,xdata,ydata)
            self.data['Tzz']=popt[0]*self.data['dt']
            self.data['Lzz']=self.data['Tzz']*self.Umean()
        except RuntimeError:
            print("Error - curve_fit failed")
            self.data['Tzz']=0
            self.data['Lzz']=0
        
    def detrend_periodic(self):
        def func_sin_u(Umean):
            f=Umean/2.0;
            def func_sin(x, a, b):
                return a*np.sin(2*np.pi*f*x+b)
            return func_sin
    
        def plot_sin(x, a, b,Umean):
            f=Umean/2.0;
            return a*np.sin(2*np.pi*f*x+b)
            
        xdata=self.t()
        Umean=self.Umean()
        self.data['u'][:,0]=signal.detrend(self.data['u'][:,0])
        ydata=self.ux()
        popt, pcov = curve_fit(func_sin_u(Umean),xdata,ydata)
        self.data['ux_old']=self.data['u'][:,0]
        self.data['ux_sin']=plot_sin(xdata,popt[0],popt[1],Umean)
        self.data['u'][:,0]=self.data['u'][:,0]-plot_sin(xdata,popt[0],popt[1],Umean)
        
    def detrend_sin(self):

        def func_sin(x, a, b, f):
                    return a*np.sin(2*np.pi*f*x+b)
            
        xdata=self.t()
        Umean=self.Umean()
        self.data['u'][:,0]=signal.detrend(self.data['u'][:,0])
        ydata=self.ux()
        popt, pcov = curve_fit(func_sin,xdata,ydata)
        self.data['ux_old']=np.copy(self.data['u'][:,0])
        self.data['ux_sin']=func_sin(xdata,popt[0],popt[1],popt[2])
        self.data['u'][:,0]=self.data['u'][:,0]-func_sin(xdata,popt[0],popt[1],popt[2])
        
def getDataPoints(filepath):
    '''
    Get a list of all the points included in a probe file "probeFile" generated by the OpenFOAM sample tool
    
    Arguments:
        * filepath: [str()] path to file "probeFile"
    
    Returns:
        * pointlist: [list(), shape=(N,3)] list of points (let's say N points) included in "probeFile"
    '''
    f = open(filepath, 'r')
    xlist=[]
    ylist=[]
    zlist=[]
    lineno=0
    for line in f:
        # This regex finds all numbers in a given string.
        # It can find floats and integers writen in normal mode (10000) or with power of 10 (10e3).
        match = re.findall('[-+]?\d*\.?\d+e*[-+]?\d*', line)
        #print(match)
        if lineno==0:
            xlist = match
        if lineno==1:
            ylist = match
        if lineno==2:
           zlist = match
           break
        lineno+=1
    f.close()
    pointlist = np.zeros(shape=(len(xlist),3))
    pointlist[:,0]=xlist
    pointlist[:,1]=ylist
    pointlist[:,2]=zlist

    return pointlist        

def getVectorPointProbeList(filename):
    '''
    Arguments:
        * filename: [string] path to file which contains all the points of the line.
        filename is normally generate by the OpenFOAM sample tool for probes.
    Returns
        * pts: [list] list of PointProbe object
    '''
    pointlist=getDataPoints(filename)
    pts=[PointProbe()]*len(pointlist)
    
    for i in range(0,len(pointlist)):
        pts[i]=PointProbe()
        pts[i].probeLoc=pointlist[i]
        
    # read file 
    crs = open(filename, 'r')
    lineno = 0
    for line in crs:
        # This regex finds all numbers in a given string.
        # It can find floats and integers writen in normal mode (10000) or with power of 10 (10e3).
        match = np.array(re.findall('[-+]?\d*\.?\d+e*[-+]?\d*', line))
        match=match.astype(np.float)
        #print(match)

        if lineno>3 and len(match)>0:
            for i in range(0,len(pointlist)):
                pts[i].probeTimes.append(match[0])
                pts[i].probeVar.append(match[1+i*3:4+i*3])
        else:
            pass
        lineno = lineno+1
    crs.close()
    
    for i in range(0,len(pointlist)):
        pts[i].probeTimes = np.array(pts[i].probeTimes)
        pts[i].probeVar = np.array(pts[i].probeVar)
        pts[i].createDataDict()
        
    return pts
    
def getPIVVectorPointProbeList(directory,pointlist,nr,frq):
    filelist=Surface.getVC7filelist(directory,nr)

    pts=[PointProbe()]*len(pointlist)
    
    for i in range(0,len(pointlist)):
        pts[i]=PointProbe()
        pts[i].probeLoc=pointlist[i,:]
        
    # read file
    
    for i,pivfile in enumerate(filelist):
        print("reading " + pivfile)
        tempS=Surface.Surface()
        tempS.readFromVC7(os.path.join(directory,pivfile))
        
        for j,pt in enumerate(pts):
            pt.probeTimes.append(i*1.0/frq)
            #print pt.probeTimes
            
            #print [tempS.vx[pt.probeLoc[0],pt.probeLoc[1]],tempS.vy[pt.probeLoc[0],pt.probeLoc[1]],tempS.vz[pt.probeLoc[0],pt.probeLoc[1]]]
            vx=tempS.vx[pt.probeLoc[1],pt.probeLoc[0]]
            vy=tempS.vy[pt.probeLoc[1],pt.probeLoc[0]]
            vz=tempS.vz[pt.probeLoc[1],pt.probeLoc[0]]
            if np.isnan(vx):
                vx=0
            if np.isnan(vy):
                vy=0
            if np.isnan(vz):
                vz=0
            pt.probeVar.append([vx,vy,vz])

    for i in range(0,len(pointlist)):
        pts[i].probeTimes = np.array(pts[i].probeTimes)
        pts[i].probeVar = np.array(pts[i].probeVar)
        pts[i].createDataDict()
        
    return pts        


def readcsv(csvfile,delimiter,fieldnames=None):
    '''
    Read a csv file with headers on the first line. If no headers, a list of headers must be specified with fieldnames.
    csv files are  very common data file for scientists. This method is quick limited, for special cases, see standard python 
    module "csv": http://docs.python.org/2/library/csv.html
    
    
    Arguments:
        * csvfile: [string] path to csvfile
        * delimiter: [string] the delimiter
        * fieldnames: [list of string] list of header if any in csvfile
        
    Returns:
        * data: [collection.defaultdict(list)] Advenced python dict with headers as dict keys.
    
    Examples:
        * >>> data = readcsv(data.csv,delimiter=';')   #cvs with header and ';' delimiter
        * >>> data = readcsv(data.csv,delimiter='\t', fieldnames=['x','y','U'])   #cvs without header and a tab as delimiter
          >>> listOfHeaders = data.keys()
          >>> dataForHeaderA = data['A']
    '''
    data = collections.defaultdict(list)
    with open(csvfile) as f:
        reader = csv.DictReader(f,delimiter=delimiter,fieldnames=fieldnames)
        #headers = reader.fieldnames
        for row in reader:
            for (k,v) in row.items():
                data[k].append(float(v))
    return data
