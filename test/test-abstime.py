import sys
sys.path.append("src/")

from timegraph.abstime import *

ap = AbsTime(['2022', '3', '2', '20', '1', '30'])
print(ap)
print(ap.to_datetime())

ap1 = AbsTime()
print(ap1)

ap2 = AbsTime(['2022', '1', 'c', '4', '30'])
print(ap2)
print(ap2.to_datetime_bounds())
print(ap2.to_num())
print(ap2.to_record())

ap3 = AbsTime(['2022', '1', '3', '4', '30'])

print(ap3)
ap3.sub_dur(10000)
print(ap3)

# print(get_extremum([2022, 1, 'c', 4, 30],
#                    [2022, 1, 'd', 4, 30]))

# print(replace_unknowns([2022, 'd', 'c', 4, 30],
#                        [2022, 1, 'c', 4, 30]))

# print(ap.duration(ap1))
# print(ap1.duration(ap))

# print(max([ap, ap1]))