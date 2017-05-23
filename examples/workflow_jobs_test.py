#encoding:UTF-8

import numpy as np

import time

import requests

from keras.optimizers import *
from keras.models import Sequential
from keras.layers.core import Dense, Dropout, Activation

from pyspark import SparkContext
from pyspark import SparkConf

from pyspark.ml.feature import StandardScaler
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.feature import StringIndexer
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.mllib.evaluation import BinaryClassificationMetrics

from distkeras.trainers import *
from distkeras.predictors import *
from distkeras.transformers import *
from distkeras.evaluators import *
from distkeras.utils import *
import distkeras.utils
from distkeras.job_deployment import Job

# Modify these variables according to your needs.
application_name = "Distributed Keras Notebook"
using_spark_2 = False
local = False
if local:
    # Tell master to use local resources.
    master = "local[*]"
    num_cores = 3
    num_executors = 1
else:
    # Tell master to use YARN.
<<<<<<< HEAD
    master = "yarn-client"
=======
<<<<<<< HEAD
    master = "yarn-client"
=======
    master = "yarn"
    deploymode = "client"
>>>>>>> e3f94d75c2ca136c1b6e55e522da926daaad2bc6
>>>>>>> 99246d56a3d196e3ea31040262bae82387d965f6
    num_executors = 6
    num_cores = 2
    
# This variable is derived from the number of cores and executors, and will be used to assign the number of model trainers.
num_workers = num_executors * num_cores

print("Number of desired executors: " + `num_executors`)
print("Number of desired cores / executor: " + `num_cores`)
print("Total number of workers: " + `num_workers`)

import os

# Use the DataBricks CSV reader, this has some nice functionality regarding invalid values.
os.environ['PYSPARK_SUBMIT_ARGS'] = '--packages com.databricks:spark-csv_2.10:1.4.0 pyspark-shell'


conf = SparkConf()
conf.set("spark.app.name", application_name)
conf.set("spark.master", master)
<<<<<<< HEAD
=======
<<<<<<< HEAD
=======
conf.set("spark.submit.deployMode", deploymode)
>>>>>>> e3f94d75c2ca136c1b6e55e522da926daaad2bc6
>>>>>>> 99246d56a3d196e3ea31040262bae82387d965f6
conf.set("spark.executor.cores", `num_cores`)
conf.set("spark.executor.instances", `num_executors`)
conf.set("spark.locality.wait", "0")
conf.set("spark.serializer", "org.apache.spark.serializer.KryoSerializer");

# Check if the user is running Spark 2.0 +
if using_spark_2:
    sc = SparkSession.builder.config(conf=conf) \
            .appName(application_name) \
            .getOrCreate()
else:
    # Create the Spark context.
    sc = SparkContext(conf=conf)
    #sc.conf = conf
    # Add the missing imports
    from pyspark import SQLContext
    sqlContext = SQLContext(sc)

# Check if we are using Spark 2.0
if using_spark_2:
    reader = sc
else:
    reader = sqlContext
# Read the dataset.
raw_dataset = reader.read.format('com.databricks.spark.csv') \
                    .options(header='true', inferSchema='true').load("atlas_higgs.csv")


# Double-check the inferred schema, and get fetch a row to show how the dataset looks like.
raw_dataset.printSchema()

# First, we would like to extract the desired features from the raw dataset.
# We do this by constructing a list with all desired columns.
features = raw_dataset.columns
features.remove('EventId')
features.remove('Weight')
features.remove('Label')
# Next, we use Spark's VectorAssembler to "assemble" (create) a vector of all desired features.
# http://spark.apache.org/docs/latest/ml-features.html#vectorassembler
vector_assembler = VectorAssembler(inputCols=features, outputCol="features")
# This transformer will take all columns specified in features, and create an additional column "features" which will contain all the desired features aggregated into a single vector.
dataset = vector_assembler.transform(raw_dataset)

# Show what happened after applying the vector assembler.
# Note: "features" column got appended to the end.
dataset.select("features").take(1)

# Apply feature normalization with standard scaling. This will transform a feature to have mean 0, and std 1.
# http://spark.apache.org/docs/latest/ml-features.html#standardscaler
standard_scaler = StandardScaler(inputCol="features", outputCol="features_normalized", withStd=True, withMean=True)
standard_scaler_model = standard_scaler.fit(dataset)
dataset = standard_scaler_model.transform(dataset)
#减小dataset的大小
dataset = dataset[dataset['Weight']>7]
dataset.count()

dataset = dataset[dataset['Weight']>7]
dataset.count()

dataset.printSchema()

# If we look at the dataset, the Label column consists of 2 entries, i.e., b (background), and s (signal).
# Our neural network will not be able to handle these characters, so instead, we convert it to an index so we can indicate that output neuron with index 0 is background, and 1 is signal.
# http://spark.apache.org/docs/latest/ml-features.html#stringindexer
label_indexer = StringIndexer(inputCol="Label", outputCol="label_index").fit(dataset)
dataset = label_indexer.transform(dataset)

# Show the result of the label transformation.
dataset.select("Label", "label_index").take(5)

# Define some properties of the neural network for later use.
nb_classes = 2 # Number of output classes (signal and background)
nb_features = len(features)

# We observe that Keras is not able to work with these indexes.
# What it actually expects is a vector with an identical size to the output layer.
# Our framework provides functionality to do this with ease.
# What it basically does, given an expected vector dimension, 
# it prepares zero vector with the specified dimensionality, and will set the neuron
# with a specific label index to one. (One-Hot encoding)

# For example:
# 1. Assume we have a label index: 3
# 2. Output dimensionality: 5
# With these parameters, we obtain the following vector in the DataFrame column: [0,0,0,1,0]

transformer = OneHotTransformer(output_dim=nb_classes, input_col="label_index", output_col="newlabel")
dataset = transformer.transform(dataset)
# Only select the columns we need (less data shuffling) while training.
dataset = dataset.select("features_normalized", "label_index", "newlabel")

# Show the expected output vectors of the neural network.
dataset.select("label_index", "newlabel").take(1)

# Shuffle the dataset.
dataset = shuffle(dataset)

# Note: we also support shuffling in the trainers by default.
# However, since this would require a shuffle for every training we will only do it once here.
# If you want, you can enable the training shuffling by specifying shuffle=True in the train() function.

# Finally, we create a trainingset and a testset.
(training_set, test_set) = dataset.randomSplit([0.6, 0.4])
training_set.cache()
test_set.cache()

model = Sequential()
model.add(Dense(500, input_shape=(nb_features,)))
model.add(Activation('relu'))
model.add(Dropout(0.4))
model.add(Dense(500))
model.add(Activation('relu'))
model.add(Dense(nb_classes))
model.add(Activation('softmax'))

model.summary()

optimizer = 'adagrad'
loss = 'categorical_crossentropy'

def evaluate_accuracy(model):
    global test_set
    
    # Allocate a Distributed Keras Accuracy evaluator.
    evaluator = AccuracyEvaluator(prediction_col="prediction_index", label_col="label_index")
    # Clear the prediction column from the testset.
    test_set = test_set.select("features_normalized", "label_index", "newlabel")
    # Apply a prediction from a trained model.
    predictor = ModelPredictor(keras_model=trained_model, features_col="features_normalized")
    test_set = predictor.predict(test_set)
    # Allocate an index transformer.
    index_transformer = LabelIndexTransformer(output_dim=nb_classes)
    # Transform the prediction vector to an indexed label.
    test_set = index_transformer.transform(test_set)
    # Fetch the score.
    score = evaluator.evaluate(test_set)
    
    return score

def add_result(trainer, accuracy, dt):
    global results;
    
    # Store the metrics.
    results[trainer] = {}
    results[trainer]['accuracy'] = accuracy;
    results[trainer]['time_spent'] = dt
    # Display the metrics.
    print("Trainer: " + str(trainer))
    print(" - Accuracy: " + str(accuracy))
    print(" - Training time: " + str(dt))
    
trainer = AEASGD(keras_model=model, worker_optimizer=optimizer, loss=loss, num_workers=num_workers, 
                 batch_size=32, features_col="features_normalized", label_col="newlabel", num_epoch=1,
                 communication_window=32, rho=5.0, learning_rate=0.1)
trainer.set_parallelism_factor(1)
job = Job("3Q20LA3MXU3N8Y9NVJ7A1T5WNHL2IWQSNNJ5V9I5P7MRJ8LSC33EN2DT3EWYLCJA",
          "user1",
          "data_path/training_set.parquet",
          1,
          16,
          trainer)
<<<<<<< HEAD
job.send('http://ec2-52-79-121-94.ap-northeast-2.compute.amazonaws.com:8000')
=======
<<<<<<< HEAD
job.send('http://ec2-52-79-121-94.ap-northeast-2.compute.amazonaws.com:8000')
=======
job.send('http://ec2-13-124-109-95.ap-northeast-2.compute.amazonaws.com:8000')
>>>>>>> e3f94d75c2ca136c1b6e55e522da926daaad2bc6
>>>>>>> 99246d56a3d196e3ea31040262bae82387d965f6
job.wait_completion()
trained_model = job.get_trained_model()
history = job.get_history()        
