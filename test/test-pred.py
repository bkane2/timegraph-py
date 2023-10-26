import sys
sys.path.append("src/")

from timegraph.pred import *

print(split_time_pred('before'))

print(split_time_pred('overlapped-by-1'))

print(build_pred('before', -1, 0))

print(more_strict('before'))