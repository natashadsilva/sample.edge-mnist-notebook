import io
import os
import sys
import time
import datetime
import PIL
import joblib
import streamsx.ec
import numpy as np
import base64

if 'scripts' not in sys.path:
    sys.path.insert(0, 'scripts')

import image_processing


# Class operator to handle the model and score tuples
class DigitPredictor(object):
    """
    Callable class that loads the model from a file, loaded model used to predict the digits.    
    
    """

    def __init__(self, model_path):
        # Note this method is only called when the topology is
        # declared to create a instance to use in the map function.
        self.model_path = model_path
        self._clf = None

    def __call__(self, t):
        """Predict the digit from the image.
        """
        start_time = time.monotonic()
        digit_prediction = self._clf.predict_proba(np.array(t['prepared_image']).reshape(1, -1))[0] # a numpy array
        t['predictions'] = digit_prediction.tolist()
        t['result_class'] = int(np.argmax(digit_prediction))
        t['result_probability'] = float(digit_prediction[t['result_class']])
        t['predict_time'] = time.monotonic() - start_time
        return t

    def __enter__(self):
        """Load the model from a file.
        """
        # Called at runtime in the IBM Streams job before
        # this instance starts processing tuples.
        print("Loading model:", os.path.join(streamsx.ec.get_application_directory(), self.model_path), flush=True)
        self._clf = joblib.load(
            os.path.join(streamsx.ec.get_application_directory(), self.model_path)
        )

    def __exit__(self, exc_type, exc_value, traceback):
        # __enter__ and __exit__ must both be defined.
        pass

# Read in the image blob and do image manipulation to prepare for scoring
class ImagePrep(object):
    def __init__(self):
        pass
    def __call__(self, t):
        start_time = time.monotonic()
        with io.BytesIO(base64.b64decode(t['image'])) as f:
            with PIL.Image.open(f) as image:
                prepped_image = image_processing.file_loaded_preprep(image)
                resized_image = image_processing.square_fit_resize(prepped_image)
                t['prepared_image'] = np.array(image_processing.center_by_pixel_mass(resized_image)).tolist()
        t['prep_time'] = time.monotonic() - start_time
        return t

# Compute per-camera digit count metrics from a set of results in a window
# We also distinguish between cases where we were fairly certain and cases where we were not.
def compute_metrics(tuples, threshold, duration, delay, repeat, parallelism, source):
    if len(tuples) > 0:
        prep_times = np.array([x['prep_time'] for x in tuples])
        predict_times = np.array([x['predict_time'] for x in tuples])
        counts = dict()
        for t in tuples:
            if t['camera'] not in counts:
                counts[t['camera']] = {'certain': [0 for i in range(11)],
                                       'uncertain': [0 for i in range(11)]}
            if t['result_probability'] > threshold:
                counts[t['camera']]['certain'][t['result_class']] += 1
            else:
                counts[t['camera']]['uncertain'][t['result_class']] += 1
        
        return {
                  'camera_metrics': counts,
                  'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                  'config': {
                    'delay': delay,
                    'repeat': repeat,
                    'source': source,
                    'confidence': threshold,
                    'classify_parallel': parallelism,
                    'metrics_duration': duration
                  },
                  'latency_metrics': {
                    'prep': {
                      'min': float(prep_times.min()),
                      'max': float(prep_times.max()),
                      'mean': float(prep_times.mean()),
                      'std': float(prep_times.std()),
                      'percentiles': np.percentile(prep_times, [50, 75, 90, 99]).tolist()
                    },
                    'predict': {
                      'min': float(predict_times.min()),
                      'max': float(predict_times.max()),
                      'mean': float(predict_times.mean()),
                      'std': float(predict_times.std()),
                      'percentiles': np.percentile(predict_times, [50, 75, 90, 99]).tolist()
                    }
                  }
                }
    else:
        return None
      
