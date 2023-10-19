import sys
sys.path.append("src/")

from timegraph.abstime import AbsTime

ap = AbsTime(('2022', '3', '2', '20', '1', '30'))
print(ap)

ap1 = AbsTime()
print(ap1)

print(ap.duration(ap1))
print(ap1.duration(ap))

print(max([ap, ap1]))