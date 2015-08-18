"""

.. module:: constraints
	:platform: Unix
	:synopsis: This module implements the usual statistical tools you need to calculate cosmological parameters confidence intervals


.. moduleauthor:: Andrea Petri <apetri@phys.columbia.edu>


"""

from __future__ import division,print_function,with_statement

from operator import mul
from functools import reduce

import cPickle as pickle

#########################################################

import numpy as np
import pandas as pd
from numpy.linalg import solve,inv
from scipy.interpolate import interp1d,Rbf

from emcee.ensemble import _function_wrapper


#########################################################

from .ensemble import Series,Ensemble,Panel 

#########################################################
#############Default Gaussian data likelihood############
#########################################################

def gaussian_likelihood(chi2,norm=1.0):

	return norm*np.exp(-0.5*chi2)

######################################################################
##########Default chi2 calculation with the sandwich product##########
######################################################################

def chi2(parameters,*args,**kwargs):

	model_feature = _predict(parameters,kwargs["num_bins"],kwargs["interpolator"])
	inverse_covariance = kwargs["inverse_covariance"]

	if model_feature.ndim == 1:
		observed_feature = kwargs["observed_feature"]
	else: 
		observed_feature = kwargs["observed_feature"][np.newaxis,:]

	inverse_covariance_dot = np.dot(observed_feature - model_feature,inverse_covariance)

	return ((observed_feature - model_feature) * inverse_covariance_dot).sum(-1)
	

	

#######################################################################
#############Feature prediction wrapper################################
#######################################################################

def _predict(parameters,num_bins,interpolator):

	#For each feature bin, compute its interpolated value
	if parameters.ndim == 1:
		
		interpolated_feature = np.zeros(num_bins)

		for n in range(num_bins):
			interpolated_feature[n] = interpolator[n]()(*parameters)
		
	else:
			
		interpolated_feature = np.zeros((parameters.shape[0],num_bins))

		for n in range(num_bins):
			interpolated_feature[:,n] = interpolator[n]()(*parameters.transpose())

	return interpolated_feature


##############################################
###########Analysis base class################
##############################################

class Analysis(Ensemble):
	
	"""
	The base class of this module; the idea in weak lensing analysis is that one has a set of simulated data, that serves as training model, and then uses that set to fit the observations for the best model parameters. Inherits from :py:class:`Ensemble`

	"""

	_analysis_type = None

	def _check_valid(self):
		assert "parameters" in self.columns.levels[0],"There are no parameters specified for this analysis!"
		assert "features" in self.columns.levels[0],"There are no features specified for this analysis!"

	##################################
	########Constructor###############
	##################################

	def __init__(self,*args,**kwargs):

		#Do not instantiate this directly
		if self._analysis_type is None:
			raise TypeError("Don't instantiate this class directly, use one of its subclasses!")

		#Parent constructor
		super(Analysis,self).__init__(*args,**kwargs)

		#Check validity of instance
		#self._check_valid()

	#def __repr__(self):
		
		#prefix = "{0}: {1} parameters, {2} bins, {3} observations\n".format(self._analysis_type,self.parameter_set.shape[1],self.feature_set.shape[1],self.nobs)
		#return prefix + super(Analysis,self).__repr__()

	@classmethod
	def from_features(cls,features,parameters=None,feature_index=None,parameter_index=None):

		#Cast shapes correctly
		if len(features.shape)==1:
			features = features[None]

		if parameters is None:
			parameters = np.arange(len(features))[None]
			parameter_index = ["p"]

		if len(parameters.shape)==1:
			parameters = parameters[None]

		if feature_index is None:
			feature_index = np.arange(features.shape[1])

		#Build indices
		parameter_index = pd.Index(parameter_index,name="parameters")
		feature_index = pd.Index(feature_index,name="features")
		parameter_and_feature_index = Series.make_index(parameter_index,feature_index)

		#Instantiate Analysis
		return cls(np.hstack((parameters,features)),columns=parameter_and_feature_index)

	##################
	####Properties####
	##################

	@property
	def parameter_set(self):
		return self["parameters"].values

	@property
	def feature_set(self):
		return self["features"].values


	##################
	####Operations####
	##################

	def add_models(self,parameters,feature):

		"""
		Add a model to the training set of the current analysis

		:param parameters: parameter set of the new model
		:type parameters: array

		:param feature: measured feature of the new model
		:type feature: array

		"""

		#Cast dimensions
		if len(parameters.shape)==1:
			parameters = parameters[None]

		if len(feature.shape)==1:
			feature = feature[None]

		#Check for input valudity
		assert len(parameters)==len(feature)
		assert parameters.shape[1] == self.parameter_set.shape[1]
		assert feature.shape[1:] == self.feature_set.shape[1:]

		#hstack
		parameters_and_features = np.hstack((parameters,feature))

		#Return the newly created Analysis
		return self.append(self._constructor(parameters_and_features,columns=self.columns),ignore_index=True)


	def reparametrize(self,transformation,**kwargs):

		"""
		Reparametrize the parameter set of the analysis by calling the formatter handle on the current parameter set (can be used to enlarge/shrink/relabel the parameter set)

		:param transformation: transformation function called on the parameters, must take in a row of parameters and return another row of parameters
		:type transformation: callable

		:param kwargs: the keyword arguments are passed to the transformation callable
		:type kwargs: dict.

		:returns: reparametrized Analysis

		"""

		reparametrized_analysis = self.copy()
		reparametrized_analysis["parameters"] = self["parameters"].apply(transformation,axis=1,**kwargs)
		return reparametrized_analysis


	def transform(self,transformation,**kwargs):

		"""
		Allows a general transformation on the feature_set of the analysis by calling an arbitrary transformation function

		:param transformation: callback function called on the feature_set; must take in a row of features and return a row of features
		:type transformation: callable 

		:param kwargs: the keyword arguments are passed to the transformation callable
		:type kwargs: dict.

		:returns: transformed Analysis

		"""

		transformed_analysis = self.copy()
		transformed_analysis["features"] = self["features"].apply(transformation,axis=1,**kwargs)
		return transformed_analysis


	def find(self,parameters,rtol=1.0e-05):

		"""
		Finds the index of the training model that has the specified combination of parameters

		:param parameters: the parameters of the model to find
		:type parameters: array.

		:param rtol: tolerance of the search (must be less than 1)
		:type rtol: float.

		:returns: array of int. with the indices of the corresponding models

		"""

		assert len(parameters)==self.parameter_set.shape[1]

		search_result = np.all(np.isclose(self.parameter_set,parameters,rtol=rtol),axis=1)
		return np.where(search_result==True)[0]


###################################################
#############Fisher matrix analysis################
###################################################

class FisherSeries(Series):

	@property
	def _constructor_expanddim(self):
		return FisherAnalysis

class FisherAnalysis(Analysis):

	################################################################
	##############DataFrame subclassing#############################
	################################################################

	@property 
	def _constructor_sliced(self):
		return FisherSeries

	@property
	def _constructor_expanddim(self):
		return FisherPanel

	#################################################################

	_analysis_type = "Fisher"
	_fiducial = 0

	"""
	The class handler of a Fisher matrix analysis, inherits from the base class Analysis

	"""

	def add_model(self,parameters,feature):

		super(FisherAnalysis,self).add_model(parameters,feature)

		try:
			self.check()
		except Exception,e:
			self.remove_model(-1)
			raise RuntimeError(e)


	def set_fiducial(self,n):

		"""
		Sets the fiducial model (with respect to which to compute the derivatives), default is 0 (i.e. self.parameter_set[0])

		:param n: the parameter set you want to use as fiducial
		:type n: int.

		"""

		assert n < self.parameter_set.shape[0],"There are less than {0} models in your analysis".format(n+1)

		self._fiducial = n

	@property
	def fiducial(self):

		return self.feature_set[self._fiducial]

	@property
	def _variations(self):

		"""
		Checks the parameter variations with respect to the fiducial cosmology

		:returns: bool array (True if the parameter is varied, False otherwise)

		"""

		return self.parameter_set!=self.parameter_set[self._fiducial]

	@property
	def variations(self):

		"""
		Checks the parameter variations with respect to the fiducial cosmology

		:returns: iterable with the positions of the variations

		"""

		for n,b in enumerate(self._variations.sum(1)):
			if b:
				yield n


	def check(self):

		"""
		Asserts that the parameters are varied one at a time, and that a parameter is not varied more than once

		:raises: AssertionError

		"""

		assert (self._variations.sum(1)<2).all(),"You can vary only a parameter at a time!"

		#Check how many variations are there for each parameter
		num_par_variations = self._variations.sum(0)
		if (num_par_variations<2).all():
			return 0
		else:
			return 1

	def where(self,par=None):

		"""
		Finds the locations of the varied parameters in the parameter set

		:returns: dict. with the locations of the variations, for each parameter

		"""

		loc = dict()
		v = np.where(self._variations==1)

		#Decide if keys are lists or simple numbers
		if self.check():

			for n in range(self.parameter_set.shape[1]):
				loc[n] = list()

			for n in range(len(v[0])):
				loc[v[1][n]].append(v[0][n])

		else:

			for n in range(len(v[0])):
				loc[v[1][n]] = v[0][n]

		if par is None:
			return loc
		else:
			return loc[par]


	@property
	def varied(self):

		"""
		Returns the indices of the parameters that are varied 

		:returns: list with the indices of the varied parameters

		"""

		loc = self.where().keys()
		loc.sort()
		
		return loc 


	def compute_derivatives(self):

		"""
		Computes the feature derivatives with respect to the parameter sets using one step finite differences; the derivatives are computed with respect to the fiducial parameter set

		:returns: array of shape (p,N), where N is the feature dimension and p is the number of varied parameters

		"""

		assert self.parameter_set.shape[0] > 1,"You need at least 2 models to proceed in a Fisher Analysis!"
		assert self.check()==0,"Finite differences implemented only at first order! Cannot compute derivatives"

		#Find the varied parameters and their locations
		loc_varied = self.where()
		par_varied = loc_varied.keys()
		par_varied.sort()

		#Allocate space for the derivatives
		derivatives = np.zeros((len(par_varied),)+self.feature_set.shape[1:])

		#cycle to parameters to calculate derivatives
		for n,p in enumerate(par_varied):
			
			#Calculate the finite difference derivative with respect to this parameter
			derivatives[n]  = (self.feature_set[loc_varied[p]] - self.feature_set[self._fiducial]) / (self.parameter_set[loc_varied[p],p] - self.parameter_set[self._fiducial,p])

		#set the derivatives attribute and return the result
		self.derivatives = derivatives
		return derivatives


	def chi2(self,observed_feature,features_covariance):

		"""
		Computes the chi2 between an observed feature and the fiducial feature, using the provided covariance

		:param observed_feature: observed feature to fit, its last dimension must have the same shape as self.feature_set[0] 
		:type observed_feature: array

		:param features_covariance: covariance matrix of the simulated features, must be provided for a correct fit!
		:type features_covariance: 2 dimensional array (or 1 dimensional if diagonal)

		:returns: chi2 of the comparison
		:rtype: float.

		"""

		assert features_covariance is not None,"No science without the covariance matrix, you must provide one!"

		#Cast the observed feature in suitable shape
		if len(observed_feature.shape)==1:
			observed_feature = observed_feature[None]
			single = True
		else:
			single = False

		#Check for correct shape of input
		assert observed_feature.shape[-1:]==self.feature_set.shape[-1:]
		assert features_covariance.shape in [self.feature_set.shape[-1:],self.feature_set.shape[-1:]*2]

		#Compute the difference
		difference = observed_feature - self.fiducial[None]

		#Compute the chi2
		if features_covariance.shape==self.feature_set.shape[-1:]:
			result = ((difference**2)/features_covariance[None]).sum(-1)
		else:
			result = (difference * solve(features_covariance,difference.transpose()).transpose()).sum(-1)

		#Return the result
		if single:
			return result[0]
		else:
			return result

	
	def fit(self,observed_feature,features_covariance):

		"""
		Maximizes the gaussian likelihood on which the Fisher matrix formalism is based, and returns the best fit for the parameters given the observed feature

		:param observed_feature: observed feature to fit, must have the same shape as self.feature_set[0]
		:type observed_feature: array

		:param features_covariance: covariance matrix of the simulated features, must be provided for a correct fit!
		:type features_covariance: 2 dimensional array (or 1 dimensional if assumed diagonal)

		:returns: array with the best fitted parameter values

		"""

		assert features_covariance is not None,"No science without the covariance matrix, you must provide one!"

		#Check for correct shape of input
		assert observed_feature.shape==self.feature_set.shape[1:]
		assert features_covariance.shape==observed_feature.shape * 2 or features_covariance.shape==observed_feature.shape

		#If derivatives are not computed, compute them
		if not hasattr(self,"derivatives"):
			self.compute_derivatives()

		#Linear algebra manipulations (parameters = M x features)
		if features_covariance.shape == observed_feature.shape * 2:
			Y = solve(features_covariance,self.derivatives.transpose())
		else:
			Y = (1/features_covariance[:,np.newaxis]) * self.derivatives.transpose()

		XY = np.dot(self.derivatives,Y)
		M = solve(XY,Y.transpose())

		#Compute difference in parameters (with respect to the fiducial model)
		dP = np.dot(M,observed_feature - self.feature_set[self._fiducial])

		#Return the actual best fit
		return self.parameter_set[self._fiducial,self.varied] + dP


	def classify(self,observed_feature,features_covariance,labels=range(2),confusion=False):

		"""
		Performs a Fisher classification of the observed feature, choosing the most probable label based on the value of the chi2
		
		:param observed_feature: observed feature to fit, the last dimenstion must have the same shape as self.feature_set[0]
		:type observed_feature: array

		:param features_covariance: covariance matrix of the simulated features, must be provided for a correct classification!
		:type features_covariance: 2 dimensional array (or 1 dimensional if assumed diagonal)

		:param labels: labels of the classification, must be the indices of the available classes (from 0 to feature_set.shape[0])
		:type labels: iterable

		:param confusion: if True, an array with the label percentage occurrences is returned; if False an array of labels is returned
		:type confusion: bool.

		:returns: array with the labels resulting from the classification
		:rtype: int.

		"""

		fiducial_original = self._fiducial

		#Compute all the chi squared values, for each observed feature and each label
		all_chi2 = list()
		for l in labels:
			self.set_fiducial(l)
			all_chi2.append(self.chi2(observed_feature,features_covariance))

		self.set_fiducial(fiducial_original)

		#Cast the list into an array
		all_chi2 = np.array(all_chi2)

		#Find the minima
		chi2_min = all_chi2.argmin(0)

		#Translate into the corresponding classes
		classes = np.zeros_like(chi2_min)
		for n,l in enumerate(labels):
			classes[chi2_min==n] = l

		if confusion:

			#Compute confusion array
			confusion_array = np.zeros(n+1)
			for n,l in enumerate(labels):
				confusion_array[n] = (classes==l).sum() / len(classes)

			#Return
			return confusion_array
		
		else:	
			#Return
			return classes



	def fisher_matrix(self,simulated_features_covariance,observed_features_covariance=None):

		"""
		Computes the Fisher matrix of the associated features, that in the end allows to compute the paramter confidence contours (around the fiducial value)

		:param simulated_features_covariance: covariance matrix of the simulated features, must be provided for a correct fit!
		:type simulated_features_covariance: 2 dimensional array (or 1 dimensional if assumed diagonal)

		:param observed_features_covariance: covariance matrix of the simulated features, if different from the simulated one; if None the simulated feature covariance is used
		:type observed_features_covariance: 2 dimensional array (or 1 dimensional if assumed diagonal)

		:returns: 2 dimensional array with the Fisher matrix of the analysis

		"""

		#Check for correct shape of input
		assert simulated_features_covariance is not None,"No science without the covariance matrix, you must provide one!"
		assert simulated_features_covariance.shape == self.feature_set.shape[1:] * 2 or simulated_features_covariance.shape == self.feature_set.shape[1:]

		#If derivatives are not computed, compute them
		if not hasattr(self,"derivatives"):
			self.compute_derivatives()

		#Linear algebra manipulations (parameters = M x features)
		if simulated_features_covariance.shape ==  self.feature_set.shape[1:] * 2:
			Y = solve(simulated_features_covariance,self.derivatives.transpose())
		else:
			Y = (1/simulated_features_covariance[:,np.newaxis]) * self.derivatives.transpose()
		
		XY = np.dot(self.derivatives,Y)

		#If we are using the same covariance matrix for observations and simulations, then XY is the Fisher matrix; otherwise we need to compute M too
		if observed_features_covariance is None:
			
			return XY
		
		else:

			assert observed_features_covariance.shape == self.feature_set.shape[1:] * 2 or observed_features_covariance.shape == self.feature_set.shape[1:]
			
			M = solve(XY,Y.transpose())
			
			if observed_features_covariance.shape == self.feature_set.shape[1:] * 2:
				parameter_covariance = np.dot(M,np.dot(observed_features_covariance,M.transpose()))
			else:
				parameter_covariance = np.dot(M * observed_features_covariance,M.transpose())

			return inv(parameter_covariance)


	def reparametrize(self,formatter,*args,**kwargs):

		#Call the parent method
		super(FisherAnalysis,self).reparametrize(formatter,*args,**kwargs)

		#Check that the format of the parameter set is valid
		self.check()


class FisherPanel(Panel):

	@property 
	def _constructor_sliced(self):
		return FisherAnalysis


#######################################################
#############Full analysis#############################
#######################################################

class EmulatorSeries(Series):

	@property
	def _constructor_expanddim(self):
		return Emulator

class Emulator(Analysis):

	_analysis_type = "Emulator"

	"""
	The class handler of a full likelihood analysis; the parameter likelihood function is calculated with an interpolation of various kind between simulation points

	"""

	################################################################
	##############DataFrame subclassing#############################
	################################################################

	@property 
	def _constructor_sliced(self):
		return EmulatorSeries

	@property
	def _constructor_expanddim(self):
		return EmulatorPanel

	##################################
	########Constructor###############
	##################################

	def __init__(self,*args,**kwargs):
		
		super(Emulator,self).__init__(*args,**kwargs) 
		self._likelihood_function = gaussian_likelihood
		self._metadata.append("_likelihood_function")

	#######################################################################################################################################

	def set_likelihood(self,function=None):

		"""
		Sets the likelihood function to a custom function input by the user: the default is the usual exp(-0.5*chi^2)

		"""

		assert function is not None
		self._likelihood_function = function

	def train(self,use_parameters="all",**kwargs):

		"""
		Builds the interpolators for each of the feature bins using a radial basis function approach

		:param use_parameters: which parameters actually vary in the supplied parameter set (it doesn't make sense to interpolate over the constant ones)
		:type use_parameters: list. or "all"

		:param kwargs: keyword arguments to be passed to the interpolator constructor

		"""

		#input sanity check
		if use_parameters != "all":
			assert type(use_parameters) == list
			used_parameters = self.parameter_set[:,use_parameters].transpose()
		else:
			used_parameters = self.parameter_set.transpose()

		#Compute total number of feature bins and reshape the training set accordingly
		self._num_bins = reduce(mul,self.feature_set.shape[1:])
		flattened_feature_set = self.feature_set.reshape((self.feature_set.shape[0],self._num_bins))

		#Build one interpolator for each feature bin (not optimal but we suck it up for now)
		self._interpolator = list()
		if "_interpolator" not in self._metadata:
			self._metadata.append("_interpolator")

		for n in range(self._num_bins):
			self._interpolator.append(_interpolate_wrapper(Rbf,args=(tuple(used_parameters) + (flattened_feature_set[:,n],)),kwargs=kwargs))

		return None


	def predict(self,parameters):

		"""
		Predicts the feature at a new point in parameter space using the bin interpolators, trained with the simulated features

		:param parameters: new points in parameter space on which to compute the chi2 statistic; it'a (N,p) array where N is the number of points and p the number of parameters, or array of size p if there is only one point
		:type parameters: array  

		"""

		#If you didn't do training before, train now with the default settings
		if not hasattr(self,"_interpolator"):
			self.train()

		#Interpolate to compute the features
		interpolated_feature = _predict(parameters,self._num_bins,self._interpolator)

		#Return the result
		if parameters.ndim == 1:
			return interpolated_feature.reshape(self.feature_set.shape[1:])
		else:
			return interpolated_feature.reshape((parameters.shape[0],) + self.feature_set.shape[1:])


	def chi2(self,parameters,observed_feature,features_covariance,split_chunks=None,pool=None):

		"""
		Computes the chi2 part of the parameter likelihood with the usual sandwich product with the covariance matrix; the model features are computed with the interpolators

		:param parameters: new points in parameter space on which to compute the chi2 statistic
		:type parameters: (N,p) array where N is the number of points and p the number of parameters

		:param observed_feature: observed feature on which to condition the parameter likelihood
		:type observed_feature: array

		:param features_covariance: covariance matrix of the features, must be supplied
		:type features_covariance: array

		:param split_chunks: if set to an integer bigger than 0, splits the calculation of the chi2 into subsequent chunks, each that takes care of an equal number of points. Each chunk could be taken care of by a different processor
		:type split_chunks: int.

		:returns: array with the chi2 values, with the same shape of the parameters input

		"""

		#Sanity checks
		assert observed_feature is not None 
		assert features_covariance is not None,"No science without the covariance matrix, you must provide one!"
		assert observed_feature.shape == self.feature_set.shape[1:]
		assert features_covariance.shape == observed_feature.shape * 2

		#If you didn't do training before, train now with the default settings
		if not hasattr(self,"_interpolator"):
			self.train()

		#Reformat the parameter input into a list of chunks
		if parameters.ndim==1:
			num_points = 1
		else:
			num_points = parameters.shape[0]

		if split_chunks is None:
			
			parameter_chunks = [parameters]
		
		elif split_chunks > 0:
			
			assert num_points%split_chunks == 0,"split_chunks must divide exactly the number of points!!"
			chunk_length = num_points//split_chunks
			parameter_chunks = [ parameters[n*chunk_length:(n+1)*chunk_length] for n in range(split_chunks) ]

		else:

			raise ValueError("split_chunks must be >0!!")

		#Compute the inverse of the covariance matrix once and for all
		covinv = inv(features_covariance)

		#Build the keyword argument dictionary to be passed to the chi2 calculator
		kwargs = {"num_bins":self._num_bins,"interpolator":self._interpolator,"inverse_covariance":covinv,"observed_feature":observed_feature}

		#Hack to make the chi2 pickleable (from emcee)
		chi2_wrapper = _function_wrapper(chi2,tuple(),kwargs)

		#Finally map chi2 calculator on the list of chunks
		if pool is not None:
			M = pool.map
		else:
			M = map
		
		chi2_list = M(chi2_wrapper,parameter_chunks)

		return np.array(chi2_list).reshape(num_points)


	def chi2Contributions(self,parameters,observed_feature,features_covariance): 

		"""
		Computes the individual contributions of each feature bin to the chi2; the model features are computed with the interpolators. The full chi2 is the sum of the individual contributions

		:param parameters: new points in parameter space on which to compute the chi2 statistic
		:type parameters: (N,p) array where N is the number of points and p the number of parameters

		:param observed_feature: observed feature on which to condition the parameter likelihood
		:type observed_feature: array

		:param features_covariance: covariance matrix of the features, must be supplied
		:type features_covariance: array

		:returns: numpy 2D array with the contributions to the chi2 (off diagonal elements are the contributions of the cross correlation between bins)

		"""

		#Sanity checks
		assert observed_feature is not None 
		assert features_covariance is not None,"No science without the covariance matrix, you must provide one!"
		assert observed_feature.shape == self.feature_set.shape[1:]
		assert features_covariance.shape == observed_feature.shape * 2

		#If you didn't do training before, train now with the default settings
		if not hasattr(self,"_interpolator"):
			self.train()

		#Compute each bin contribution to the chi2
		residuals = observed_feature - self.predict(parameters)

		#Compute the inverse covariance
		covinv = inv(features_covariance)

		#Compute the hits map
		return np.outer(residuals,residuals) * covinv



	def likelihood(self,chi2_value,**kwargs):

		"""
		Computes the likelihood value with the selected likelihood function, given the pre-computed chi2 value

		:param chi2_value: chi squared values 
		:type chi2_value: array

		:param kwargs: keyword arguments to be passed to your likelihood function

		"""

		return self._likelihood_function(chi2_value,**kwargs)


	def set_to_model(self,parameters):

		"""
		Set the current model of the emulator to the one specified by the parameter set

		:param parameters: parameters for which the feature will be emulated
		:type parameters: array.

		"""

		#assert parameters.shape[0]==self.parameter_set.shape[1]
		
		#if not hasattr(self,"_interpolator"):
		#	self.train()
		
		#self._current_model_parameters = parameters
		#self._current_predicted_feature = self.predict(parameters)
		#self._current_interpolated_feature = interp1d(self.feature_label,self._current_predicted_feature)

		raise NotImplementedError


	def emulate(self,new_feature_label):

		"""
		Compute an emulated feature at the new feature label specified (multipoles, thresholds, ...) for the current model, using a linear interpolation between bins

		:param new_feature_label: new feature label for which you want to emulate the feature
		:type new_feature_label: array.

		:returns: the emulated feature

		""" 

		#return self._current_interpolated_feature(new_feature_label)
		raise NotImplementedError


class EmulatorPanel(Panel):

	@property 
	def _constructor_sliced(self):
		return Emulator
