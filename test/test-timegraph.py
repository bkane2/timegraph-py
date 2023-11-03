import sys
sys.path.append("src/")

from timegraph.timegraph import TimeGraph
from timegraph.abstime import AbsTime

tg = TimeGraph()

tg.register_event('e1')
tg.register_event('e2')
tg.register_event('e3')
tg.enter('e1', 'before-0', 'e2')
tg.enter('e2', 'before-0', 'e3')
# tg.enter('e1', 'after', AbsTime([1997, 7, 2, 1, 1, 1]))
# tg.enter('e1', 'before', AbsTime([2023, 1, 1, 1, 1, 1]))
# tg.enter('e2', 'after', AbsTime([1998, 7, 2, 1, 1, 1]))
# tg.enter('e2', 'before', AbsTime([2023, 2, 1, 1, 1, 1]))
tg.enter('e1start', 'same-time', AbsTime([1997, 7, 2, 1, 1, 1]))
tg.enter('e1end', 'same-time', AbsTime([1999, 7, 2, 1, 1, 1]))
tg.enter('e2start', 'same-time', AbsTime([1999, 8, 2, 1, 1, 1]))
tg.enter('e2end', 'same-time', AbsTime([2001, 7, 2, 1, 1, 1]))


# tg.register_event('e1')
# tg.register_event('e2')
# tg.register_event('e3')
# tg.enter('e2', 'between', 'e1', 'e3')
# # e1start > e1end > e2start > e2end > e3start > e3end

print(tg.format_timegraph(verbose=True))
print(tg.relation('e2', 'e1'))
print(tg.elapsed('e1', 'e2'))
print(tg.duration_of('e1'))
print(tg.evaluate('e1', 'before', 'e2'))
print(tg.evaluate('e1', 'after', 'e2'))
print(tg.evaluate('e1', 'equal', 'e2'))
print(tg.evaluate('e2', 'before', 'e1'))
# print(tg.start_of('e2'))