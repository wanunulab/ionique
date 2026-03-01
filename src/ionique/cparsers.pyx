# cparsers.pyx
# Contact: Jacob Schreiber
#          jmschreiber91@gmail.com
# modified for ionique by Ali Fallahi.
"""
Cython implementations of ionic current parsers.

This module contains optimized Cython implementations of the segmentation parser (SpeedyStatSplit) defined
in parsers.py. Variance-based recursive segmentation is provided by
`FastStatSplit`, which is approximately 50-100x faster than the equivalent
pure-Python implementation. 

Modules
-------
FastStatSplit
    Cython implementation of the StatSplit variance-based segmenter.
pairwise
    Utility generator yielding consecutive pairs from an iterable.
"""

import numpy as np
cimport numpy as np

from libc.math cimport log
cimport cython

from itertools import tee, chain
from ionique.core import Segment, MetaSegment

# Implement the max and min functions as cython
cdef inline int int_max( int a, int b ): return a if a >= b else b
cdef inline int int_min( int a, int b ): return a if a <= b else b


# Calculate the mean of a segment of current
@cython.boundscheck(False)
cdef inline double mean_c( int start, int end, double [:] c ): 
	return ( c[end-1] - c[start-1] ) / ( end-start) if start != 0 else c[end-1]/end if start != end else 0

# Calculate the variance of a segment of current
@cython.boundscheck(False)
cdef inline double var_c( int start, int end, double [:] c, double [:] c2 ):
	if start == end:
		return 0
	if start == 0:
		return c2[end-1]/end - (c[end-1]/end) ** 2
	return (c2[end-1]-c2[start-1])/(end-start) - \
		((c[end-1]-c[start-1])/(end-start))**2

def pairwise(iterable):
	"""
	Return an iterator of overlapping pairs from the input iterable.

	Parameters
	----------
	iterable : iterable
	    Any iterable to consume. Each element is paired with its immediate
	    successor, so an input of length n yields n-1 pairs.

	Returns
	-------
	zip
	    An iterator of (a, b) tuples where b immediately follows a in the
	    original iterable.
	"""
	a, b = tee(iterable)
	next(b, None)
	return zip(a, b)

cdef class FastStatSplit:
	"""
	Cython implementation of the variance-based signal segmenter by Kevin Karplus.

	Approximately 50-100x faster than the equivalent pure-Python implementation
	depending on parameters. Segments a 1D ionic current trace by recursively
	finding split points that maximize the reduction in total variance across
	the two resulting sub-segments.

	Parameters
	----------
	min_width : int, optional
	    Minimum number of samples required in any segment. Defaults to 100.
	max_width : int, optional
	    Maximum number of samples allowed in any segment before a forced split
	    is inserted. Defaults to 1000000.
	window_width : int, optional
	    Width of the sliding window used during stepwise split search.
	    Must be >= 2 * min_width. Defaults to 10000.
	min_gain_per_sample : float or None, optional
	    If provided, uses the legacy method for setting the gain threshold
	    (deprecated). Defaults to None.
	false_positive_rate : float or None, optional
	    Expected number of false-positive split detections per second. Used in
	    Bayesian gain threshold calculation. Defaults to sampling_freq.
	prior_segments_per_second : float or None, optional
	    Prior expectation of how many true segments occur per second. Used in
	    Bayesian gain threshold calculation. Defaults to sampling_freq / 2.
	sampling_freq : float, optional
	    Sampling frequency of the signal in Hz. Defaults to 1e5.
	cutoff_freq : float or None, optional
	    Low-pass cutoff frequency in Hz used to adjust the Bayesian threshold.
	    Must be <= 0.5 * sampling_freq if provided. Defaults to None.

	Attributes
	----------
	min_gain : float
	    Minimum log-likelihood gain required to accept a split point, computed
	    from the Bayesian formulation or the legacy min_gain_per_sample method.
	"""

	cdef int min_width, max_width, window_width, sampling_freq
	cdef public double min_gain
	cdef double [:] c, c2

	def __init__( self, min_width=100, max_width=1000000, window_width=10000,
		min_gain_per_sample=None, false_positive_rate=None,
		prior_segments_per_second=None, sampling_freq=1.e5, cutoff_freq=None ):
		"""
		Initialize FastStatSplit and compute the minimum gain threshold.

		Parameters
		----------
		min_width : int, optional
		    Minimum number of samples in any segment. Defaults to 100.
		max_width : int, optional
		    Maximum number of samples before a forced split. Defaults to 1000000.
		window_width : int, optional
		    Width of the sliding search window. Must be >= 2 * min_width.
		    Defaults to 10000.
		min_gain_per_sample : float or None, optional
		    Legacy gain-per-sample threshold (deprecated). If provided,
		    `min_gain` is set to `min_gain_per_sample * window_width`.
		    Defaults to None.
		false_positive_rate : float or None, optional
		    Expected false-positive splits per second for the Bayesian
		    threshold. Defaults to `sampling_freq`.
		prior_segments_per_second : float or None, optional
		    Prior rate of true segments per second for the Bayesian threshold.
		    Defaults to `sampling_freq / 2`.
		sampling_freq : float, optional
		    Sampling frequency of the signal in Hz. Defaults to 1e5.
		cutoff_freq : float or None, optional
		    Low-pass cutoff frequency in Hz for threshold adjustment.
		    Must be <= 0.5 * sampling_freq. Defaults to None.
		"""

		self.min_width = min_width
		self.max_width = max_width
		self.window_width = window_width
		self.sampling_freq = sampling_freq

		if not false_positive_rate:
			false_positive_rate = sampling_freq
		if not prior_segments_per_second: 
			prior_segments_per_second = sampling_freq / 2.

		assert self.max_width >= self.min_width, "Maximum width must be greater\
			than minimum width."
		assert self.window_width >= 2*self.min_width, "Window width must be\
			greater than twice the minimum width."

		if cutoff_freq:
			assert cutoff_freq <= 0.5*sampling_freq, "Cutoff freq must be\
				less than half the sampling frequency."

		# Now set min_gain appropriately, either using the old method or
		# by calculating a new one in a Bayesian manner as described here:
		# http://gasstationwithoutpumps.wordpress.com/2014/02/01/more-on-
		# segmenting-noisy-signals/
		if min_gain_per_sample:
			# Use old method for setting gain (DEPRECATED)
			self.min_gain = min_gain_per_sample * self.window_width

		else:
			# Set the ratio between the cutoff frequency and the Nyquist
			# frequency.
			k = cutoff_freq / ( 0.5 * sampling_freq ) if cutoff_freq else 1
			
			# Shorten the name
			sps = prior_segments_per_second

			# Set the gain threshold in a Bayesian manner
			self.min_gain = \
				( -log( sps / ( sampling_freq - sps ) ) \
				  -log( false_positive_rate / sampling_freq ) ) / k 

		# Convert from sigma to variance, since this is in log space multiply
		# by two instead of square.
		self.min_gain *= 2

	def parse( self, current ):
		"""
		Segment a current trace and return a list of Segment objects.

		Computes cumulative sum arrays for efficient variance calculations,
		then recursively finds split points and constructs one `Segment` per
		detected sub-segment, each containing its slice of the current array.

		Parameters
		----------
		current : numpy.ndarray
		    1D array of ionic current values to segment.

		Returns
		-------
		list[Segment]
		    A list of `Segment` objects covering the full input array with no
		    gaps or overlaps.
		"""

		cdef list break_points
		self.c = np.cumsum( current )
		self.c2 = np.cumsum( np.multiply( current, current ) )

		breakpoints = self._recursive_split( 0, int(len(current)) )

		segments = [ Segment( current=current[start:end], start=start, duration=(end-start),
			end=end ) for start, end in pairwise( chain([0],breakpoints,[len(current)]) ) ]

		return segments

	def parse_meta( self, current ):
		"""
		Segment a current trace and return lightweight MetaSegment objects.

		Identical to `parse` but constructs `MetaSegment` instances instead of
		`Segment` instances, so no signal data is stored in each node.

		Parameters
		----------
		current : numpy.ndarray
		    1D array of ionic current values to segment.

		Returns
		-------
		list[MetaSegment]
		    A list of `MetaSegment` objects covering the full input array with
		    no gaps or overlaps.
		"""
		cdef list break_points
		self.c = np.cumsum( current )
		self.c2 = np.cumsum( np.multiply( current, current ) )

		breakpoints = self._recursive_split( 0, int(len(current)) )

		segments = [ MetaSegment( current=current[start:end], start=start, duration=(end-start),
			end=end ) for start, end in pairwise( chain([0],breakpoints,[len(current)]) ) ]

		return segments

	def best_single_split( self, current ):
		"""
		Find the single best split point in the entire current array.

		Parameters
		----------
		current : numpy.ndarray
		    1D array of ionic current values to analyze.

		Returns
		-------
		tuple[float, int]
		    A tuple of (gain, index) where gain is the log-likelihood gain in
		    variance achieved by splitting at the returned index, and index is
		    the position in the current array at which the split should occur.
		"""

		self.c = np.cumsum( current )
		self.c2 = np.cumsum( np.multiply( current, current ) )

		return self._best_single_split()

	cdef tuple _best_single_split( self ):
		"""Return the single highest-gain split across the entire stored cumulative arrays, ignoring the min_gain threshold."""

		cdef int start = 0, end = len( self.c ) - 1, i, x = -1
		cdef double var_summed, low_var_summed, high_var_summed, gain
		cdef double min_gain = 0.

		var_summed = end * log( var_c( 0, end, self.c, self.c2))
		
		for i in xrange( 2, end-2):
			low_var_summed = i * log( var_c( 0, i, self.c, self.c2 ) )
			high_var_summed = ( end-i ) * log( var_c( i, end, self.c, self.c2 ) )
			gain = var_summed-( low_var_summed+high_var_summed )
			if gain > min_gain:
				min_gain = gain
				x = i

		return min_gain, x

	@cython.boundscheck(False)
	cdef int _best_split_stepwise( self, int start, int end ):
		"""Find the index of the best variance-reducing split between start and end, or -1 if none meets min_gain."""

		if end-start <= 2*self.min_width:
			return -1 
		cdef double var_summed = (end - start) * log( var_c(start, end, self.c, self.c2) )
		cdef double min_gain = self.min_gain
		cdef int i, x = -1
		cdef double low_var_summed, high_var_summed, gain

		for i in xrange( start+self.min_width, end+1-self.min_width ):
			low_var_summed = ( i-start ) * log( var_c( start, i, self.c, self.c2 ) )
			high_var_summed = ( end-i ) * log( var_c( i, end, self.c, self.c2 ) )
			gain = var_summed-( low_var_summed+high_var_summed )
			if gain > min_gain:
				min_gain = gain
				x = i
		return x

	cdef list _recursive_split( self, int start, int end ):
		"""Recursively split the segment [start, end) and return a sorted list of all breakpoint indices."""

		cdef int pseudostart, pseudoend, split_at = -1

		for pseudostart in xrange( start, end-2*self.min_width, self.window_width//2 ):
			if pseudostart > start + self.max_width:
				split_at = int_min( start+self.max_width, end-self.min_width )
				return [ split_at ] + self._recursive_split( split_at, end )

			pseudoend = int_min( end, pseudostart+self.window_width )
			split_at = self._best_split_stepwise( pseudostart, pseudoend )
			if split_at >= 0:
				break

		if split_at == -1:
			if end-start <= self.max_width:
				return []
			split_at = int_min( start+self.max_width, end-self.min_width )
		return self._recursive_split( start, split_at ) + [ split_at ] + \
			self._recursive_split( split_at, end )

	def score_samples( self, current, no_split=False ):
		"""
		Return per-sample log-likelihood gain scores for each recursive scan.

		For each recursive sweep across the data, a score array is produced
		recording the variance-gain value evaluated at every candidate split
		position. One score array is returned per scan; splits detected during
		a scan trigger further recursive scans of the resulting sub-segments.

		Parameters
		----------
		current : numpy.ndarray
		    1D array of ionic current values to score.
		no_split : bool, optional
		    If True, perform only a single (non-recursive) scan and return one
		    score array without looking for further splits. Defaults to False.

		Returns
		-------
		list[numpy.ndarray]
		    A list of score arrays, one per recursive scan. Each array has the
		    same length as the stored cumulative array and contains the
		    log-likelihood gain at each sample index.
		"""

		self.c = np.cumsum( current )
		self.c2 = np.cumsum( np.multiply( current, current ) )
		return self._recursive_split_scoring( 0, len(current), no_split )

	@cython.boundscheck(False)
	cdef tuple _best_split_stepwise_score( self, int start, int end ):
		"""Find the best split between start and end and return (split_index, score_array) with per-sample gain values."""

		if end-start <= 2*self.min_width:
			return -1, []
		cdef double var_summed = (end - start) * log( var_c(start, end, self.c, self.c2) )
		cdef double min_gain = self.min_gain
		cdef int i, x = -1
		cdef double low_var_summed, high_var_summed, gain
		cdef np.ndarray score = np.zeros( len(self.c) )

		for i in xrange( start+self.min_width, end+1-self.min_width ):
			low_var_summed = ( i-start ) * log( var_c( start, i, self.c, self.c2 ) )
			high_var_summed = ( end-i ) * log( var_c( i, end, self.c, self.c2 ) )
			gain = var_summed-( low_var_summed+high_var_summed )
			score[i] = gain
			if gain > min_gain:
				min_gain = gain
				x = i
		return x, score

	cdef list _recursive_split_scoring( self, int start, int end, int no_split ):
		"""Recursively split [start, end) and accumulate per-scan score arrays, mirroring _recursive_split logic."""

		cdef int pseudostart, pseudoend, split_at = -1
		cdef np.ndarray score
		cdef list scores = [] 

		if no_split:
			split_at, score = self._best_split_stepwise_score( start, end )
			return list(score) 

		for pseudostart in xrange( start, end-2*self.min_width, self.window_width//2 ):
			if pseudostart > start + self.max_width:
				split_at = int_min( start+self.max_width, end-self.min_width )
				return scores + self._recursive_split_scoring( split_at, end, 0 )

			pseudoend = int_min( end, pseudostart+self.window_width )
			split_at, score = self._best_split_stepwise_score( pseudostart, pseudoend )
			scores.append( score )

			if split_at >= 0:
				break

		if split_at == -1:
			if end-start <= self.max_width:
				return scores
			split_at = int_min( start+self.max_width, end-self.min_width )

		return scores + self._recursive_split_scoring( start, split_at, 0 ) + \
			self._recursive_split_scoring( split_at, end, 0 )
