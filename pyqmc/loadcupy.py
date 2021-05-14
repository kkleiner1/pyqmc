try:
    import cupy as cp
    from cupy import get_array_module, asnumpy, fuse
except ModuleNotFoundError as e:
    import numpy as cp

    def get_array_module(a):
        return cp

    def asnumpy(a):
        return a

    def fuse():
        return lambda x: x
