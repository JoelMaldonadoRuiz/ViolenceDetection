# from silence_tensorflow import silence_tensorflow
# silence_tensorflow()

import tensorflow as tf
import os
from tensorflow.keras import layers

# GPUs
# gpus = tf.config.experimental.list_physical_devices('GPU')
# for gpu in gpus:
#   tf.config.experimental.set_memory_growth(gpu, True)

print(tf.config.list_physical_devices())
strategy = tf.distribute.MirroredStrategy()

# Random seed to ensure reproducibility
SEED = 100
tf.random.set_seed(SEED)

# Constants
IMG_SIZE = 224
N_FRAMES = 20
BATCH_SIZE = 16
CHANNELS = 1
AUTOTUNE = tf.data.experimental.AUTOTUNE

TRAIN_RECORD_DIR = 'Data/violence_video_train.tfrecord'
VAL_RECORD_DIR = 'Data/violence_video_val.tfrecord'

def parse_tfrecord(example):
    features = {
        'label': tf.io.FixedLenFeature([], tf.int64),
        'feature': tf.io.FixedLenFeature([], tf.string)
    }
    example = tf.io.parse_single_example(example, features)
    video = tf.io.decode_raw(example['feature'], tf.float32)
    video = tf.reshape(video, (N_FRAMES, IMG_SIZE, IMG_SIZE, CHANNELS))
    label = tf.cast(example['label'], tf.uint8)
    return video, label

def preprocess(video, label):
    video = video / 255.0
    return video, label

DATASET_SIZE = 2000

# train = tf.data.TFRecordDataset(TRAIN_RECORD_DIR)
# val = tf.data.TFRecordDataset(VAL_RECORD_DIR)

# dataset = train.concatenate(val)
# dataset = dataset.map(parse_tfrecord)
# dataset = dataset.map(preprocess)
# dataset = dataset.shuffle(buffer_size=DATASET_SIZE)


# TRAIN_SPLIT = int(0.75 * DATASET_SIZE)
# TEST_SPLIT = int(0.15 * DATASET_SIZE)
# VAL_SPLIT = int(0.15 * DATASET_SIZE)

# train_dataset = dataset.take(TRAIN_SPLIT)
# rest_dataset = dataset.skip(TRAIN_SPLIT)
# test_dataset = rest_dataset.take(TEST_SPLIT)
# val_dataset = rest_dataset.skip(VAL_SPLIT)

# train_dataset = train_dataset.shuffle(buffer_size=TRAIN_SPLIT)

# train_dataset = train_dataset.batch(BATCH_SIZE)
# test_dataset = test_dataset.batch(BATCH_SIZE)
# val_dataset = val_dataset.batch(BATCH_SIZE)

# train_dataset = train_dataset.prefetch(AUTOTUNE)
# val_dataset = val_dataset.prefetch(AUTOTUNE)

# train_dataset = train_dataset.cache()
# val_dataset = val_dataset.cache()

train_dataset = tf.data.TFRecordDataset(TRAIN_RECORD_DIR)
train_dataset = train_dataset.map(parse_tfrecord)
train_dataset = train_dataset.map(preprocess)


val_dataset = tf.data.TFRecordDataset(VAL_RECORD_DIR)
val_dataset = val_dataset.map(parse_tfrecord)
val_dataset = val_dataset.map(preprocess)

train_dataset = train_dataset.shuffle(buffer_size=1600)
val_dataset = val_dataset.shuffle(buffer_size=400)

train_dataset = train_dataset.batch(BATCH_SIZE)
val_dataset = val_dataset.batch(BATCH_SIZE)


train_dataset = train_dataset.prefetch(AUTOTUNE)
val_dataset = val_dataset.prefetch(AUTOTUNE)

# train_dataset = train_dataset.cache()
# val_dataset = val_dataset.cache()

class RandomFlipVideo(tf.keras.layers.Layer):
  def __init__(self, **kwargs):
    super(RandomFlipVideo, self).__init__()

  def call(self, inputs):
    if tf.random.uniform(()) > 0.5:
      return tf.map_fn(lambda x: tf.image.flip_left_right(x), inputs)
    return inputs
  
class RandomRotationVideo(tf.keras.layers.Layer):
  def __init__(self, max_rotation=0.3, **kwargs):
    super(RandomRotationVideo, self).__init__()
    self.max_rotation = max_rotation

  def call(self, inputs):
    return tf.map_fn(self.rotate, inputs)
    
  def rotate(self, video):
    random_factor = self.max_rotation * self.max_rotation * 2 - self.max_rotation
    return tfa.image.rotate(video, random_factor)
  
  def get_config(self):
    config = super().get_config().copy()
    return config

# Model Creation
def create_model():

    CONV_NEURONS = 148
    LSTM_NEURONS = 100
    DENSE_NEURONS = 256
    DROPOUT = 0.5
    N_LAYERS = 3

    model = tf.keras.models.Sequential()


    model.add(layers.InputLayer(input_shape=(N_FRAMES, IMG_SIZE, IMG_SIZE, CHANNELS)))
    model.add(RandomFlipVideo())
    model.add(RandomRotationVideo(0.3))
    
    # for i in range(N_LAYERS):
    #     model.add(layers.TimeDistributed(layers.Conv2D(CONV_NEURONS, (3, 3), activation='relu')))
    #     model.add(layers.BatchNormalization())
    #     model.add(layers.TimeDistributed(layers.Conv2D(CONV_NEURONS, (3, 3), activation='relu')))
    #     model.add(layers.BatchNormalization())
    #     model.add(layers.TimeDistributed(layers.MaxPooling2D((2, 2))))
    

    # model.add(layers.TimeDistributed(layers.Flatten()))

    # model.add(layers.LSTM(LSTM_NEURONS, return_sequences=True))
    # # model.add(layers.TimeDistributed(layers.BatchNormalization()))

    # model.add(layers.LSTM(LSTM_NEURONS, return_sequences=True))
    # # model.add(layers.TimeDistributed(layers.BatchNormalization()))
    
    # model.add(layers.LSTM(LSTM_NEURONS, return_sequences=True))
    # # model.add(layers.TimeDistributed(layers.BatchNormalization()))
    
    # model.add(layers.TimeDistributed(layers.Dense(DENSE_NEURONS, activation='relu')))
    # model.add(layers.TimeDistributed(layers.Dropout(DROPOUT)))

    # model.add(layers.TimeDistributed(layers.Dense(DENSE_NEURONS, activation='relu')))
    # model.add(layers.TimeDistributed(layers.Dropout(DROPOUT)))
    # model.add(layers.TimeDistributed(layers.Dense(DENSE_NEURONS, activation='relu')))
    # model.add(layers.TimeDistributed(layers.Dropout(DROPOUT)))

    # model.add(layers.TimeDistributed(layers.Dense(1, activation='sigmoid')))

    model.add(layers.ConvLSTM2D(
        filters=16, 
        kernel_size=3,
        padding='same'))
    model.add(layers.TimeDistributed(layers.Dropout(0.5)))

    model.add(layers.Flatten())

    model.add(layers.Dense(224))
    model.add(layers.Dropout(0.5))

    model.compile(
        loss='binary_crossentropy',
        optimizer=tf.keras.optimizers.Adam(),
        metrics=['accuracy'],
    )

    return model

import tensorflow_addons as tfa


early_stopper = tf.keras.callbacks.EarlyStopping('val_accuracy', patience=20, restore_best_weights=True)
reduce_lr_on_plataeu = tf.keras.callbacks.ReduceLROnPlateau(monitor='val_accuracy', factor=0.2, patience=5)

from datetime import datetime
time_date = datetime.now().strftime("%I-%M-%p")

check_point = tf.keras.callbacks.ModelCheckpoint(f'Checkpoints/violence_model_{time_date}.h5', save_best_only=True)


with strategy.scope():
    model = create_model()

history = model.fit(train_dataset, 
                    validation_data=val_dataset, 
                    epochs=25, 
                    callbacks=[check_point, early_stopper, reduce_lr_on_plataeu, tf.keras.callbacks.TensorBoard("tb_logs")], 
                    use_multiprocessing=True, 
                    workers=16,
                    batch_size=BATCH_SIZE,
                    )



model.save(f'PersonDetection_temp.h5')

metrics = model.evaluate(val_dataset)

model.save(f'Models/Violence_Acc_{metrics[1]}.h5')

import pickle
with open('history_pickle.pkl', 'w') as f:
  pickle.dump(history, f)