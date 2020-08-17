import numpy as np
from PIL import Image, ImageOps
import io

# Training and test data set files, all labeled
FN_TEST_LABELS = 'data/mnist/t10k-labels-idx1-ubyte'
FN_TEST_IMAGES = 'data/mnist/t10k-images-idx3-ubyte'
FN_TRAIN_LABELS = 'data/mnist/train-labels-idx1-ubyte'
FN_TRAIN_IMAGES = 'data/mnist/train-images-idx3-ubyte'


# This function will read the entire file in and return a single multi-dimensional array,
# of the appropriate data type, rank, and dimensionality for the given file.
# Note that this may consume a lot of memory, and may take a while to read in the whole
# file before it returns.
def read_idx_file(filename, start=0, count=None):
    # Helper map of type enum values to dtype strings for numpy
    dtypes = {8:'>u1', 9:'>i1', 0xb:'>i2',0xc:'>i4',0xd:'>f4',0xe:'>f8'}
    dtypesizes = {8:1, 9:1, 0xb:2,0xc:4,0xd:4,0xe:8}
    
    with open(filename, 'rb') as f:
        # Ok, let's parse one of these files
        # first read a uint32be as the magic number, yielding data type (size of each value, and format), and number of dimensions
        dummy, = np.fromfile(f, dtype='>u2', count=1)
        dte,dims = np.fromfile(f, dtype='>u1', count=2)
        #print(dummy, dte, dtypes[dte], dtypesizes[dte], dims)
        
        # Then comes a uint32be number per dimension, yielding the size of the n-dimensional array in that dimension
        # Only after all those dimension sizes, comes the data, all big-endian.
        # The arrays are in C-style, where the last dimension index changes most frequently.
        dsizes = np.fromfile(f, dtype='>u4', count=dims)
        unit_size = int(np.prod(dsizes[1:])) if len(dsizes) > 1 else 1
        seek_delta = int(start * unit_size * dtypesizes[dte])
        read_units = dsizes[0] if count is None else min(dsizes[0], count)
        nshape = dsizes
        nshape[0] = read_units
        #print(dsizes)
        #print(np.prod(dsizes), unit_size, seek_delta, read_units)
        
        f.seek(seek_delta, 1)

        # So now, we can loop over the outer dimensions, setting the indexes appropriately,
        # and read the inner dimension as a vector all in one go
        return np.reshape(np.fromfile(f, dtype=dtypes[dte], count=int(unit_size * read_units)), newshape=nshape, order='C')


# This version, on the other hand, is a generator, reading one unit from the file at a time.
# A "unit" in this context is all the data except the top-most dimension.
# So, a rank-1 file would just yield individual scalars on each call.
# A rank-3 file would yield rank-2 arrays on each call, consisting of the 2 lowest dimension.
# To make things concrete, the digits labels file is rank-1, with 60k units, each one a single uint8.  Each yield would generate the next uint8.
# The digits images files, however, are rank-3, with 60k units, each one a 28x28 array of uint8.  Each yield would generate the next 28x28 array of uint8.
# The optional start index (defaults to 0), will skip the first "start" count of units, and generate the one after that.
# Subsequent generations would continue from that point.
def read_idx_units(filename, start=0, count=None):
    # Helper map of type enum values to dtype strings for numpy
    dtypes = {8:'>u1', 9:'>i1', 0xb:'>i2',0xc:'>i4',0xd:'>f4',0xe:'>f8'}
    dtypesizes = {8:1, 9:1, 0xb:2,0xc:4,0xd:4,0xe:8}

    with open(filename, 'rb') as f:
        # Ok, let's parse one of these files
        # first read a uint32be as the magic number, yielding data type (size of each value, and format), and number of dimensions
        dummy, = np.fromfile(f, dtype='>u2', count=1)
        dte,dims = np.fromfile(f, dtype='>u1', count=2)
        #print(dummy, dte, dtypes[dte], dtypesizes[dte], dims)

        # Then comes a uint32be number per dimension, yielding the size of the n-dimensional array in that dimension
        # Only after all those dimension sizes, comes the data, all big-endian.
        # The arrays are in C-style, where the last dimension index changes most frequently.
        dsizes = np.fromfile(f, dtype='>u4', count=dims)
        unit_size = int(np.prod(dsizes[1:])) if len(dsizes) > 1 else 1
        seek_delta = int(start * unit_size * dtypesizes[dte])
        read_units = dsizes[0] if count is None else min(dsizes[0], count)
        #print(dsizes)
        #print(np.prod(dsizes), unit_size, seek_delta, read_units)

        f.seek(seek_delta, 1)
        
        for i in range(read_units):
            # Read the next unit
            if len(dsizes) > 1:
                yield np.reshape(np.fromfile(f, dtype=dtypes[dte], count=unit_size), newshape=dsizes[1:], order='C')
            else:
                # Special case for the scalar situation, where re-shaping doesn't make sense.
                yield np.fromfile(f, dtype=dtypes[dte], count=1)[0]

# From an MNIST image, put the data into a BytesIO filehandle and return that filehandle for later use,
# making it act just as a PNG file handle would.
def to_filehandle(image):
    of = io.BytesIO()
    ImageOps.invert(Image.fromarray(image)).convert("RGB").save(of, "PNG")
    of.seek(0)
    return of
    
    