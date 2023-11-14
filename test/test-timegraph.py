import sys
sys.path.append("src/")

from timegraph.timegraph import TimeGraph, visualize_timegraph
from timegraph.abstime import AbsTime

def test1():
  tg = TimeGraph()

  tg.register_event('e1')
  tg.register_event('e2')
  tg.register_event('e3')
  tg.register_event('e4')
  tg.register_event('now1')
  tg.register_event('now2')
  tg.register_event('now3')

  tg.enter('e1', 'during', 'now1')
  tg.enter('now1', 'before', 'now2')
  tg.enter('e2', 'during', 'now2')
  tg.enter('e3', 'during', 'now2')
  tg.enter('now2', 'before', 'now3')
  tg.enter('e4', 'during', 'now3')

  nodes, edges = tg.to_graph()
  for n in nodes:
    print(n)
  for n in edges:
    print(n)

  for tp in tg.topsort():
    print(' - '.join(sorted(list(tp.alternate_names.union([tp.name])))))

  visualize_timegraph(tg)



def test2():
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

  tg.register_event('e4')
  tg.register_event('e5')
  tg.register_event('e6')
  tg.enter('e4', 'before-0', 'e5')
  tg.enter('e5', 'before-0', 'e6')
  tg.enter('e5', 'before', 'e2')

  nodes, edges = tg.to_graph()
  for n in nodes:
    print(n)
  for n in edges:
    print(n)

  for tp in tg.topsort():
    print(' - '.join(sorted(list(tp.alternate_names.union([tp.name])))))

  visualize_timegraph(tg)



def main():
  test1()
  # test2()



if __name__ == '__main__':
  main()