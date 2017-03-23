"""Development script to deploy jobs using controller daemons."""

## BEGIN Imports. ##############################################################

from distkeras.native.jobs import Job
from distkeras.native.jobs import DataTransferJob
from distkeras.native.jobs import TrainingJob

from keras.layers.convolutional import *
from keras.layers.core import *
from keras.models import Sequential
from keras.optimizers import *

## END Imports. ################################################################

# Define the Keras model that needs to be trained.
img_rows, img_cols = 28, 28
# number of convolutional filters to use
nb_filters = 32
# size of pooling area for max pooling
pool_size = (2, 2)
# convolution kernel size
kernel_size = (3, 3)
input_shape = (img_rows, img_cols, 1)
nb_classes = 10

model = Sequential()
model.add(Convolution2D(nb_filters, kernel_size[0], kernel_size[1],
                        border_mode='valid',
                        input_shape=input_shape))
model.add(Activation('relu'))
model.add(Convolution2D(nb_filters, kernel_size[0], kernel_size[1]))
model.add(Activation('relu'))
model.add(MaxPooling2D(pool_size=pool_size))
model.add(Flatten())
model.add(Dense(225))
model.add(Activation('relu'))
model.add(Dense(nb_classes))
model.add(Activation('softmax'))
# Summarize the model.
model.summary()

# Define the training parameters.
parameters = {}
parameters['num_parameter_servers'] = 1
parameters['weight_allocations'] = [[0, 2, 4, 6]]
parameters['num_workers'] = 1

job = TrainingJob(model, parameters)
job.run()
