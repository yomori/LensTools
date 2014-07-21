"""

.. module:: convergence
	:platform: Unix
	:synopsis: This module implements the tools to compute topological statistics on 2D convergence maps: measure the power spectrum, counting peaks, measure the minkowski functionals


.. moduleauthor:: Andrea Petri <apetri@phys.columbia.edu>


"""

from __future__ import division

from external import _topology

import numpy as np
from scipy.ndimage import filters


################################################
########ConvergenceMap class####################
################################################

class ConvergenceMap(object):

	"""
	A class that handles 2D convergence maps and allows to compute their topological descriptors (power spectrum, peak counts, minkowski functionals)

	>>> from lenstools import ConvergenceMap 
	>>> from lenstools.defaults import load_fits_default_convergence

	>>> test_map = ConvergenceMap.fromfilename("map.fit",loader=load_fits_default_convergence)
	>>> imshow(test_map.kappa)

	"""

	def __init__(self,kappa,angle):

		self.kappa = kappa
		self.side_angle = angle

	@classmethod
	def fromfilename(cls,*args,**kwargs):
		
		"""
		This class method allows to read the map from a data file; the details of the loading are performed by the loader function. The only restriction to this function is that it must return a tuple (angle,kappa)

		:param args: The positional arguments that are to be passed to the loader (typically the file name)

		:param kwargs: Only one keyword is accepted "loader" is a pointer to the previously defined loader method (a template is defaults.load_fits_default_convergence)

		"""

		assert "loader" in kwargs.keys(),"You must specify a loader function!"
		loader = kwargs["loader"]

		angle,kappa = loader(*args)
		return cls(kappa,angle)

	def gradient(self):
		
		"""
		Computes the gradient of the map and sets the gradient_x,gradient_y attributes accordingly

		:returns: tuple -- (gradient_x,gradient_y)

		>>> test_map = ConvergenceMap.fromfilename("map.fit")
		>>> gx,gy = test_map.gradient()

		"""
		self.gradient_x, self.gradient_y = _topology.gradient(self.kappa)
		return self.gradient_x,self.gradient_y

	def hessian(self):
		
		"""
		Computes the hessian of the map and sets the hessian_xx,hessian_yy,hessian_xy attributes accordingly

		:returns: tuple -- (hessian_xx,hessian_yy,hessian_xy)

		>>> test_map = ConvergenceMap.fromfilename("map.fit")
		>>> hxx,hyy,hxy = test_map.hessian()

		"""
		self.hessian_xx,self.hessian_yy,self.hessian_xy = _topology.hessian(self.kappa)
		return self.hessian_xx,self.hessian_yy,self.hessian_xy

	def pdf(self,thresholds,norm=False):

		"""
		Computes the one point probability distribution function of the convergence map

		:param thresholds: thresholds extremes that define the binning of the pdf
		:type thresholds: array

		:param norm: normalization; if set to a True, interprets the thresholds array as units of sigma (the map standard deviation)
		:type norm: bool.

		:returns: tuple -- (threshold midpoints -- array, pdf normalized at the midpoints -- array)

		:raises: AssertionError if thresholds array is not provided

		>>> test_map = ConvergenceMap.fromfilename("map.fit")
		>>> thresholds = np.arange(map.kappa.min(),map.kappa.max(),0.05)
		>>> nu,p = test_map.pdf(thresholds)

		"""

		assert thresholds is not None
		midpoints = 0.5 * (thresholds[:-1] + thresholds[1:])

		if norm:
			sigma = self.kappa.std()
		else:
			sigma = 1.0

		#Compute the histogram
		hist,bin_edges = np.histogram(self.kappa,bins=thresholds*sigma,density=True)

		#Return
		return midpoints,hist*sigma


	def peakCount(self,thresholds,norm=False):
		
		"""
		Counts the peaks in the map

		:param thresholds: thresholds extremes that define the binning of the peak histogram
		:type thresholds: array

		:param norm: normalization; if set to a True, interprets the thresholds array as units of sigma (the map standard deviation)
		:type norm: bool.

		:returns: tuple -- (threshold midpoints -- array, differential peak counts at the midpoints -- array)

		:raises: AssertionError if thresholds array is not provided

		>>> test_map = ConvergenceMap.fromfilename("map.fit")
		>>> thresholds = np.arange(map.kappa.min(),map.kappa.max(),0.05)
		>>> nu,peaks = test_map.peakCount(thresholds)

		"""

		assert thresholds is not None
		midpoints = 0.5 * (thresholds[:-1] + thresholds[1:])

		if norm:
			sigma = self.kappa.std()
		else:
			sigma = 1.0

		return midpoints,_topology.peakCount(self.kappa,thresholds,sigma)

	def minkowskiFunctionals(self,thresholds,norm=False):

		"""
		Measures the three Minkowski functionals (area,perimeter and genus characteristic) of the specified map excursion sets

		:param thresholds: thresholds that define the excursion sets to consider
		:type thresholds: array

		:param norm: normalization; if set to a True, interprets the thresholds array as units of sigma (the map standard deviation)
		:type norm: bool.

		:returns: tuple -- (nu -- array, V0 -- array, V1 -- array, V2 -- array) nu are the bins midpoints and V are the Minkowski functionals

		:raises: AssertionError if thresholds array is not provided

		>>> test_map = ConvergenceMap.fromfilename("map.fit")
		>>> thresholds = np.arange(-2.0,2.0,0.2)
		>>> nu,V0,V1,V2 = test_map.minkowskiFunctionals(thresholds,norm=True)

		"""

		assert thresholds is not None
		midpoints = 0.5 * (thresholds[:-1] + thresholds[1:])

		if norm:
			sigma = self.kappa.std()
		else:
			sigma = 1.0

		#Check if gradient and hessian attributes are available; if not, compute them
		if not (hasattr(self,"gradient_x") and hasattr(self,"gradient_y")):
			self.gradient()

		if not (hasattr(self,"hessian_xx") and hasattr(self,"hessian_yy") and hasattr(self,"hessian_xy")):
			self.hessian()

		#Compute the Minkowski functionals and return them as tuple
		v0,v1,v2 = _topology.minkowski(self.kappa,self.gradient_x,self.gradient_y,self.hessian_xx,self.hessian_yy,self.hessian_xy,thresholds,sigma)

		return midpoints,v0,v1,v2

	def moments(self,connected=False,dimensionless=False):

		"""
		Measures the first nine moments of the convergence map (two quadratic, three cubic and four quartic)

		:param connected: if set to True returns only the connected part of the moments
		:type connected: bool.

		:param dimensionless: if set to True returns the dimensionless moments, normalized by the appropriate powers of the variance
		:type dimensionless: bool. 

		:returns: array -- (sigma0,sigma1,S0,S1,S2,K0,K1,K2,K3)

		>>> test_map = ConvergenceMap.fromfilename("map.fit")
		>>> var0,var1,sk0,sk1,sk2,kur0,kur1,kur2,kur3 = test_map.moments()
		>>> sk0,sk1,sk2 = test_map.moments(dimensionless=True)[2:5]
		>>> kur0,kur1,kur2,kur3 = test_map.moments(connected=True,dimensionless=True)[5:]

		"""

		#First check that the instance has the gradient and hessian attributes; if not, compute them
		if not (hasattr(self,"gradient_x") and hasattr(self,"gradient_y")):
			self.gradient()

		if not (hasattr(self,"hessian_xx") and hasattr(self,"hessian_yy") and hasattr(self,"hessian_xy")):
			self.hessian()
		
		#Quadratic moments
		sigma0 = self.kappa.std()
		sigma1 = np.sqrt((self.gradient_x**2 + self.gradient_y**2).mean())

		#Cubic moments
		S0 = (self.kappa**3).mean()
		S1 = ((self.kappa**2)*(self.hessian_xx + self.hessian_yy)).mean()
		S2 = ((self.gradient_x**2 + self.gradient_y**2)*(self.hessian_xx + self.hessian_yy)).mean()

		#Quartic moments
		K0 = (self.kappa**4).mean()
		K1 = ((self.kappa**3) * (self.hessian_xx + self.hessian_yy)).mean()
		K2 = ((self.kappa) * (self.gradient_x**2 + self.gradient_y**2) * (self.hessian_xx + self.hessian_yy)).mean()
		K3 = ((self.gradient_x**2 + self.gradient_y**2)**2).mean()

		#Compute connected moments (only quartic affected)
		if connected:
			K0 -= 3 * sigma0**4
			K1 += 3 * sigma0**2 * sigma1**2
			K2 += sigma1**4
			K3 -= 2 * sigma1**4

		
		#Normalize moments to make them dimensionless
		if dimensionless:
			S0 /= sigma0**3
			S1 /= (sigma0 * sigma1**2)
			S2 *= (sigma0 / sigma1**4)

			K0 /= sigma0**4
			K1 /= (sigma0**2 * sigma1**2)
			K2 /= sigma1**4
			K3 /= sigma1**4

			sigma0 /= sigma0
			sigma1 /= sigma1

		#Return the array
		return np.array([sigma0,sigma1,S0,S1,S2,K0,K1,K2,K3])

	def powerSpectrum(self,l_edges):

		"""
		Measures the power spectrum of the convergence map at the multipole moments specified in the input

		:param l_edges: Multipole bin edges
		:type l_edges: array

		:returns: tuple -- (l -- array,Pl -- array) = (multipole moments, power spectrum at multipole moments)

		:raises: AssertionError if l_edges are not provided

		>>> test_map = ConvergenceMap.fromfilename("map.fit")
		>>> l_edges = np.arange(200.0,5000.0,200.0)
		>>> l,Pl = test_map.powerSpectrum(l_edges)

		"""

		assert l_edges is not None
		l = 0.5*(l_edges[:-1] + l_edges[1:])

		#Calculate the Fourier transform of the map with numpy FFT
		ft_map = np.fft.rfft2(self.kappa)

		#Compute the power spectrum with the C backend implementation
		power_spectrum = _topology.rfft2_azimuthal(ft_map,ft_map,self.side_angle,l_edges)

		#Output the power spectrum
		return l,power_spectrum

	def cross(self,other,l_edges):

		"""
		Measures the cross power spectrum between two convergence maps at the multipole moments specified in the input

		:param other: The other convergence map
		:type other: ConvergenceMap instance

		:param l_edges: Multipole bin edges
		:type l_edges: array

		:returns: tuple -- (l -- array,Pl -- array) = (multipole moments, cross power spectrum at multipole moments)

		:raises: AssertionError if l_edges are not provided or the other map has not the same shape as the input one

		>>> test_map = ConvergenceMap.fromfilename("map.fit",loader=load_fits_default_convergence)
		>>> other_map = ConvergenceMap.fromfilename("map2.fit",loader=load_fits_default_convergence)
		
		>>> l_edges = np.arange(200.0,5000.0,200.0)
		>>> l,Pl = test_map.cross(other_map,l_edges)

		"""

		assert l_edges is not None
		l = 0.5*(l_edges[:-1] + l_edges[1:])

		assert isinstance(other,ConvergenceMap)
		assert self.side_angle == other.side_angle
		assert self.kappa.shape == other.kappa.shape

		#Calculate the Fourier transform of the maps with numpy FFTs
		ft_map1 = np.fft.rfft2(self.kappa)
		ft_map2 = np.fft.rfft2(other.kappa)

		#Compute the cross power spectrum with the C backend implementation
		cross_power_spectrum = _topology.rfft2_azimuthal(ft_map1,ft_map2,self.side_angle,l_edges)

		#Output the cross power spectrum
		return l,cross_power_spectrum


	def smooth(self,angle_in_arcmin,kind="gaussian",inplace=False):

		"""
		Performs a smoothing operation on the convergence map

		:param angle_in_arcmin: size of the smoothing kernel in arcminutes
		:type angle_in_arcmin: float.

		:param kind: type of smoothing to be performed (only implemented gaussian so far)
		:type kind: str.

		:param inplace: if set to True performs the smoothing in place overwriting the old convergence map
		:type inplace: bool.

		:returns: ConvergenceMap instance (or None if inplace is True)

		"""

		assert kind == "gaussian","Only gaussian smoothing implemented!!"

		#Compute the smoothing scale in pixel units
		smoothing_scale_pixel = angle_in_arcmin * self.kappa.shape[0] / (self.side_angle*60.0)

		#Perform the smoothing
		smoothed_kappa = filters.gaussian_filter(self.kappa,smoothing_scale_pixel)

		#Return the result
		if inplace:
			
			self.kappa = smoothed_kappa
			
			#If gradient attributes are present, recompute them
			if (hasattr(self,"gradient_x") or hasattr(self,"gradient_y")):
				self.gradient()

			if (hasattr(self,"hessian_xx") or hasattr(self,"hessian_yy") or hasattr(self,"hessian_xy")):
				self.hessian()
			
			return None

		else:
			return ConvergenceMap(smoothed_kappa,self.side_angle)


	def __add__(self,rhs):

		"""
		Defines addition operator between ConvergenceMap instances; the convergence values are summed

		:returns: ConvergenceMap instance with the result of the sum

		:raises: AssertionError if the operation cannot be performed

		"""

		if isinstance(rhs,ConvergenceMap):

			assert self.side_angle == rhs.side_angle
			assert self.kappa.shape == rhs.kappa.shape

			new_kappa = self.kappa + rhs.kappa

		elif type(rhs) == np.float:

			new_kappa = self.kappa + rhs

		elif type(rhs) == np.ndarray:

			assert rhs.shape == self.kappa.shape
			new_kappa = self.kappa + rhs

		else:

			raise TypeError("The right hand side cannot be added!!")

		return ConvergenceMap(new_kappa,self.side_angle)
