import sys
sys.path.append("src/")

from timegraph.timegraph import *

tg = TimeGraph()

tg.add_single('tp1')
tg.add_single('tp2')
tg.add_duration_max('tp1', 'tp2', 1000)

# print(tg.time_point('tp1').format(verbose=True))
print(tg.format_timegraph(verbose=True))