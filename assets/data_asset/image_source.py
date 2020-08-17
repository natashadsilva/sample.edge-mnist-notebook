import time
import os
import sys
import streamsx.ec

if 'scripts' not in sys.path:
    sys.path.insert(0, 'scripts')

import mnist_index_files

class ImageSource(object):
    def __init__(self, source_type, filenames, delay, repeat):
        self._delay = delay
        self._repeat = repeat
        self._filenames = filenames
        self._source_type = source_type
        self._images = None
        self._count = -1
                
    def __enter__(self):
        # Get the submission time parameters and normalize them
        self._delay = float(self._delay())
        self._repeat = int(self._repeat())
        self._source_type = int(self._source_type())
        if self._source_type > len(self._filenames):
            raise ValueError
        if self._delay == 0.0:
            self._delay = None
        if self._repeat == 0:
            self._repeat = None

        print("Entering ImageSource operator with delay=%f, repeat=%d, source=%d (from %s)" % (self._delay if self._delay is not None else 0.0,
                                                                                               self._repeat if self._repeat is not None else 0,
                                                                                               self._source_type,
                                                                                               self._filenames[self._source_type]))

        # Generate the image iterator
        self._images = self.regen_iter()
        
    
    def mnist_postprocess(self, reader):
        for value in reader:
            # MNIST objects come back. Need to make these look like PNG blobs
            #print("Found new MNIST object")
            with mnist_index_files.to_filehandle(value) as of:
                yield of.read()
        
    def extra_postprocess(self, reader):
        # these are directory scans, so the resultant files might not be what we're looking for
        for value in reader:
            if value.is_file() and value.name.endswith('.png'):
                #print("Found new file from directory scan iterator that is a valid png file", value.path)
                with open(value.path, "rb") as f:
                    yield f.read()
    
    def regen_iter(self):
        if self._repeat is None or self._repeat > 0:
            #print("Regenerating iterator")
            if self._repeat is not None:
                self._repeat -= 1
            if self._source_type < 2:
                # types 0 and 1 are MNIST sources, and the associated filename entry is the actual MNIST index filename
                return self.mnist_postprocess(mnist_index_files.read_idx_units(os.path.join(streamsx.ec.get_application_directory(), self._filenames[self._source_type])))
            else:
                # types 2 and 3 are extra png file sources, and the associated filename entry is the directory to scan.
                return self.extra_postprocess(os.scandir(os.path.join(streamsx.ec.get_application_directory(), self._filenames[self._source_type])))
        else:
            print("Done repeating.  Camera exhausted.")
            raise StopIteration
        
    def __exit__(self, exc_type, exc_value, traceback):
        # __enter__ and __exit__ must both be defined.
        pass    
    
    def __call__(self):
        return self
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self._delay is not None:
            time.sleep(self._delay)
        self._count += 1
        
        # Get the next image, either from the MNIST dataset or the next file in the directory
        img = None
        while img is None:
            try:
                img = next(self._images)                 
            except StopIteration:
                img = None
                self._images = self.regen_iter()

        #print("Submitting new image", self._count)
        return {'count': self._count, 'image': img}
        