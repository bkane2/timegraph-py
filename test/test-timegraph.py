import sys
sys.path.append("src/")

from timegraph.timegraph import *
from timegraph.abstime import *

tg = TimeGraph()

tg.register_event('e1')
tg.register_event('e2')
tg.enter('e1', 'before', 'e2')
tg.enter('e1', 'before', AbsTime([2023, 1, 1, 1, 1, 1]))
tg.enter('e1', 'after', AbsTime([1997, 7, 2, 1, 1, 1]))

# tg.add_single('tp1')
# tg.add_single('tp2')
# tg.add_duration_max('tp1', 'tp2', 1000)

# print(tg.time_point('tp1').format(verbose=True))
print(tg.format_timegraph(verbose=True))


# print(tg.timegraph['e1end'].ancestors[0].from_tp)


# TODO: debug why the above is moving e1start to a separate chain,
# and why not all the points are getting added to the timegraph