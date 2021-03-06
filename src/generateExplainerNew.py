from math import ceil, floor

from sklearn.externals import joblib
from sklearn import tree
import ast
import numpy as np
import json
from random import shuffle
import heapq
import copy
import matplotlib.pyplot as plt
import itertools
import time
import pickle

roundDigits = 2

def getKey(item):
		return item[0]


allWeights = {}

parentLists = []
allLeafIds = []
store_paths = {}

def float_round(num, places = 0, direction = floor):
    return direction(num * (10**places)) / float(10**places)



def getPerturbations(features, scoreCount):
	'''Go through all the paths and generate a list of perturbations based on features that contradict the datapoint'''
	for i in range(0,150):
		min_contradictions = 10000
		best_tuple = None
		heappp = []

		#Find all the path tumples and measure the number of contradictions
		for pathTuple in store_paths[i]:
			path, package_list, lambda_list = pathTuple
			contradictions = 0
			contra_list = []
			for l in range(0,len(lambda_list)):
				lambda_check = lambda_list[l]
				package_check = package_list[l]
				valid = lambda_check(features)
				if not valid:
					contradictions+=1
					contra_list.append(package_check[0])

			if contradictions < min_contradictions:
				min_contradictions = contradictions
				best_tuple = pathTuple

			heapq.heappush(heappp,(contradictions, contra_list))

		#For all the petrubations, add to the score based on hamming distance (Utility and confidence are the same for most forests)
		for z in range(0,10000):
			if len(heappp) > 0:
				pop = heapq.heappop(heappp)[1]
				if len(pop) > 0:
					scoreAdd = float(1/len(pop))
					for f in pop:
						scoreCount[f] += scoreAdd



def generateAllExplanations(P, model, explanationDump,scoreHistoryLocation,explanatory=[]):
	'''Generate explanations once for all, second time do it normalized'''
	generateExplainer(P, model, explanationDump,scoreHistoryLocation,False,explanatory=explanatory)
	generateExplainer(P, model, explanationDump,scoreHistoryLocation,True,explanatory=explanatory)

def generateExplainer(P, model, explanationDump,scoreHistoryLocation,haveHistory,singleDocument=[],explanatory=[]):
	'''Generate explanations data to be used by model'''

	clf = joblib.load(model) 

	allFeatures = []

	if (len(singleDocument) > 0):
		allFeatures.append(singleDocument)
	else:
		with open(explanationDump, 'r') as f:
			for line in f:
				allFeatures.append(line)


	global parentLists 
	global allLeafIds 
	global store_paths 

	e = 0

	thresholds = {}
	for i in range(0,89):
		thresholds[i] = {}


	#Go through all trees in forest
	for estimator in clf.estimators_:

		parents = {}
		feature = estimator.tree_.feature
		threshold = estimator.tree_.threshold
		value = estimator.tree_.value
		children_left = estimator.tree_.children_left
		children_right = estimator.tree_.children_right


		leafIDs = []
		z = 0

		#construct mappings of id -> parent in parents
		for i in threshold:

			if feature[z] != -2.0:
				thresholds[feature[z]][float_round(threshold[z], 1, ceil)] = 1


			if (i == -2.0):
				leafIDs.append(z)

			parents[int(children_right[z])] = z
			parents[int(children_left[z])] = z

			z+=1

		paths = []


		for leaf in leafIDs:

			#Check if the utility is = 1
			purity = (value[leaf][0][1]/(value[leaf][0][0] + value[leaf][0][1]))
			if purity != 1.0:
				continue
			currentLeaf = leaf
			c = 0
			path = []

			#Go upwards to get the whole path
			while True:
				path.append(currentLeaf)
				if currentLeaf==0:
					break
				currentLeaf = parents[currentLeaf]
				c+=1

			path = list(reversed(path))
			

			package_list = []
			lambda_list = []

			#Go through the whole path and find out which conditions aren't met and require perturbation

			for i in range(0,len(path)-1):
				sign = "<="
				if children_right[path[i]] == path[i+1]:
					sign = ">"
				package = (feature[path[i]], sign, threshold[path[i]])
				check = eval("lambda X: X[%s] %s %s" % (feature[path[i]], sign, threshold[path[i]]))

				lambda_list.append(check)
				package_list.append(package)

			paths.append((path,package_list,lambda_list))

		store_paths[e] = paths

		e+=1


	# #Find the number of unique perturbations
	# countUnique = 1
	# lenz = 0
	# z2 = 0
	# for z in thresholds:
	# 	dic = thresholds[z]
	# 	if len(dic.keys()) > 0:
	# 		countUnique = countUnique * len(dic.keys())
	# 		lenz += len(dic.keys())
	# 		print(len(dic.keys()))
	# 		z2+=1

	# print(thresholds)
	# print(lenz/z2)



	#For normalization
	if haveHistory:
		score_history_loaded = pickle.load(open(scoreHistoryLocation, "rb" ))
	score_history = []

	lineCount = 0

	totalTime = 0

	#For all the datapoints in te training

	aggregate = {}

	for i in range(0,89):
		aggregate[i] = 0.0

		#all feature vectors for all document
	for line in allFeatures:


		if lineCount >= 100:
			break
		features = json.loads(line)["featureList"]
		scoreCount = {}
		for i in range(0,len(features)):
			scoreCount[i] = 0

		start = time.time()


		getPerturbations(features, scoreCount)

		end = time.time() - start
		totalTime+=end
		print(end)
		print("TIME HERE^^^^^")
		score_history.append(scoreCount)
		lineCount+=1
		print(lineCount)


		sortedFeatures = []
		for f in scoreCount:
			if f in explanatory:
				std = 1
				mean = 0
				value = float(scoreCount[f])
				if haveHistory: 
					allPast = []
					for his in score_history_loaded:
						allPast.append(his[f])
					mean = np.average(allPast)
					std = np.std(allPast)
				normValue = (value-mean)/std
				sortedFeatures.append((normValue,f))
				aggregate[f]+= normValue


		topKFeatures = list(reversed(sorted(sortedFeatures, key=getKey)))


		#if we are trying to get the perturbation values 
		#of just one document, here we return the ranked list of tuplies of the form (featureID, normalizedScore)
		if (len(singleDocument) > 0):
			return topKFeatures


		#the rest of this is file is just testing stuff for when you run on more than one document
		#----------------------------------------------------------------

		#print(topKFeatures)
		# scores = {"topic":0,"detail":0,"emotion":0,"writing":0}
		# for i in range(0,len(topKFeatures)):
		# 	if topKFeatures[i][0] > 0:
		# 		#We compute the average score for each explanation function by doing the sum of the features score * (C/(# of features mapped to the explanation))
		# 		if topKFeatures[i][1] in emotional:
		# 			scores["emotion"]+=topKFeatures[i][0]*float(len(topic))/float(len(emotional))
		# 		if topKFeatures[i][1] in detail:
		# 			scores["detail"]+=topKFeatures[i][0]*float(len(topic))/float(len(detail))
		# 		if topKFeatures[i][1] in writing:
		# 			scores["writing"]+=topKFeatures[i][0]*float(len(topic))/float(len(writing))
		# 		if topKFeatures[i][1] in topic:
		# 			scores["topic"]+=topKFeatures[i][0]*float(len(topic))/float(len(topic))

		# sum = 0.0
		# for key in scores:
		# 	sum+=scores[key]


		# sortedFeatures = []

		# for i in aggregate.keys():
		# 	sortedFeatures.append((aggregate[i],i))
		# agg = list(reversed(sorted(sortedFeatures, key=getKey)))
		# print("HERE I AGGREGATED THEM ALL")
		# print(agg)

		# print(str(scores["topic"]/sum) + " Bad-Topic - Talk about more topics")
		# print(str(scores["detail"]/sum) + " Not detailed enough - Go into more detail")
		# print(str(scores["emotion"]/sum) + " Unfriendly - Be more friendly")
		# print(str(scores["writing"]/sum) + " Untrustworthy grammar - Please try to write more trustworthily")
		# print(json.loads(line)["reviewText"])

	pickle.dump(score_history, open( scoreHistoryLocation, "wb" ))

	print(totalTime/100)
