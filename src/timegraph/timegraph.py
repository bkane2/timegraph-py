"""Timegraph implementation"""

import math
from collections import UserList

from timegraph.constants import *
from timegraph.util import indent
from timegraph.abstime import AbsTime, duration_min, combine_durations, get_best_duration
from timegraph.pred import (test_answer, test_point_answer, inverse_reln, split_time_pred,
                            build_pred, combine_strict, combine_test_results, determine_split)

# ``````````````````````````````````````
# TimePoint
# ``````````````````````````````````````



class TimePoint:
  """A node corresponding to a particular time point in a timegraph.
  
  Attributes
  ----------
  id : str
    The ID of the time point.
  chain : MetaNode
    The meta-node for the chain that this point belongs to.
  pseudo : float
    pseudo time for this point.
  min_pseudo : float
    Pseudo time of the earliest time point this is equal to.
  max_pseudo : float
    Pseudo time of the latest point this is equal to.
  absolute_min : AbsTime, optional
    Absolute time minimum for this point.
  absolute_max : AbsTime, optional
    Absolute time maximum for this point.
  ancestors : TimeLinkList
    A list of in-chain ascendant links.
  xancestors : TimeLinkList
    A list of cross-chain ascendant links.
  descendants : TimeLinkList
    A list of in-chain descendant links.
  xdescendants : TimeLinkList
    A list of cross-chain descendant links.
  alternate_names : set[str]
    A set of names of alternative points collapsed into this.

  Parameters
  ----------
  name : str
  """

  def __init__(self, name, chain=None, pseudo=PSEUDO_INIT):
    assert (isinstance(name, str) and
            (isinstance(chain, MetaNode) or chain is None) and
            type(pseudo) in [int, float])
    self.name = name
    self.chain = chain
    self.pseudo = pseudo
    self.min_pseudo = float('-inf')
    self.max_pseudo = float('inf')
    # absolute times initially unknown (i.e., every slot is a symbolic term)
    self.absolute_min = AbsTime(['y1', 'mo1', 'd1', 'h1', 'm1', 's1'])
    self.absolute_max = AbsTime(['y2', 'mo2', 'd2', 'h2', 'm2', 's2'])
    self.ancestors = TimeLinkList()
    self.xancestors = TimeLinkList()
    self.descendants = TimeLinkList()
    self.xdescendants = TimeLinkList()
    self.alternate_names = set()
  

  def pseudo_before(self):
    """Calculate new pseudo time before this point."""
    cur = 0 if self.pseudo == PSEUDO_INIT else self.pseudo
    return cur - PSEUDO_INCREMENT


  def pseudo_after(self):
    """Calculate new pseudo time after this point."""
    cur = PSEUDO_INCREMENT if self.pseudo == PSEUDO_INIT else self.pseudo
    return cur + PSEUDO_INCREMENT
  

  def pseudo_between(self, tp):
    """Calculate a pseudo time between another time point using 90% of the difference, renumbering the chain if no space left between."""
    assert isinstance(tp, TimePoint)
    p1 = self.pseudo
    p2 = tp.pseudo

    if abs(p2-p1) < 10:
      self.chain.renumber()
      p1 = self.pseudo
      p2 = tp.pseudo
    
    if p1 == PSEUDO_INIT:
      p1 = 0
    if p2 == PSEUDO_INIT:
      p2 = 0
    return (((p2 - p1) * 9) // 10) + p1
  

  def possibly_equal(self, tp):
    """Check if this point and `tp` can possibly be equal. i.e., they are <= or >=.

    The test is done by checking to see if the pseudo time of `tp` fits in the range of
    pseudos defined by the min and max pseudos of this point.
    """
    assert isinstance(tp, TimePoint)
    p2 = tp.pseudo
    return p2 > self.min_pseudo and p2 < self.max_pseudo
  

  def find_pseudo(self, tp):
    """Find the most strict relation possible between this point and `tp` using their pseudo times."""
    assert isinstance(tp, TimePoint) 
    p1 = self.pseudo
    p2 = tp.pseudo
    if p1 == p2:
      return PRED_SAME_TIME
    elif p1 < p2:
      return PRED_BEFORE if self.possibly_equal(tp) else f'{PRED_BEFORE}-{1}'
    elif p1 > p2:
      return PRED_AFTER if self.possibly_equal(tp) else f'{PRED_AFTER}-{1}'
    else:
      return PRED_UNKNOWN
  

  def on_same_chain(self, tp):
    """Check if this point is on the same chain as `tp`."""
    assert isinstance(tp, TimePoint)
    return self.chain == tp.chain


  def first_in_chain(self):
    """Check if this is the first point on its chain."""
    return True if not self.ancestors else False
  

  def last_in_chain(self):
    """Check if this is the last point on its chain."""
    return True if not self.descendants else False
  

  def adjacent(self, tp):
    """Check whether this point and `tp` are next to each other on the chain with no intervening points."""
    assert isinstance(tp, TimePoint) 
    return self.first_desc() == tp
  

  def first_desc(self):
    """Return the first descendant of point on same chain (or self if no descendants)."""
    return self if not self.descendants else self.descendants[0].to_tp


  def first_anc(self):
    """Return the first ancestor of point on same chain (or self if no ancestors)."""
    return self if not self.ancestors else self.ancestors[0].from_tp
  

  def update_first(self):
    """If this point is earlier on its chain than the current first point, update the first pointer."""
    meta = self.chain
    first = meta.first
    if not first or self.pseudo < first.pseudo:
      meta.first = self


  def check_first(self):
    """Check that this is the first point on its chain when a point is being replaced (through equal).
    
    In that case, the first indicator is set to the point's first descendant, and the minimum pseudo is
    propagated if necessary.

    Notes
    -----
    If this were happening within the same chain, the first point would be kept, and the others made equal
    to it, so this situation would not arise.
    """
    meta = self.chain
    first = meta.first
    if self.name == first.name:
      newp = self.first_desc()
      meta.first = newp
      if newp.min_pseudo == self.min_pseudo:
        newp.first_desc().prop_min(newp.pseudo)
  

  def add_ancestor_link(self, timelink):
    """Add a link on the in chain ancestor list."""
    assert isinstance(timelink, TimeLink)
    self.ancestors.add(timelink)


  def add_descendant_link(self, timelink):
    """Add a link on the in chain descendant list."""
    assert isinstance(timelink, TimeLink)
    self.descendants.add(timelink)


  def add_xancestor_link(self, timelink):
    """Add a link on the cross chain ancestor list."""
    assert isinstance(timelink, TimeLink)
    self.xancestors.add(timelink)


  def add_xdescendant_link(self, timelink):
    """Add a link on the cross chain descendant list."""
    assert isinstance(timelink, TimeLink)
    self.xdescendants.add(timelink)


  def prop_min(self, newmin):
    """Propagate minimum pseudo time forward along descendants until it reaches a minimum greater than it."""
    assert type(newmin) in [int, float]
    if newmin > float('-inf') and newmin >= self.min_pseudo:
      self.min_pseudo = newmin
      if self.descendants:
        item = self.descendants[0]
        assert isinstance(item, TimeLink)
        item.to_tp.prop_min(newmin)


  def prop_max(self, newmax):
    """Propagate maximum pseudo time backward along ancestors until it reaches a maximum less than it."""
    assert type(newmax) in [int, float]
    if newmax < float('inf') and newmax <= self.max_pseudo:
      self.max_pseudo = newmax
      if self.ancestors:
        item = self.ancestors[0]
        assert isinstance(item, TimeLink)
        item.from_tp.prop_max(newmax)


  def add_strictness(self, tp):
    """Modify the max pseudo of self and the min pseudo of `tp` to ensure that they cannot be equal."""
    assert isinstance(tp, TimePoint)
    oldmin = tp.min_pseudo
    oldmax = self.max_pseudo
    
    # Set minimum of tp to be self, if this is more restrictive
    if oldmin == float('-inf') or self.pseudo > oldmin:
      newmin = self.pseudo
      tp.min_pseudo = newmin
      tp.prop_min(newmin)
    
    # Set maximum of self to be tp, if this is more restrictive
    if oldmax == float('inf') or tp.pseudo < oldmax:
      newmax = tp.pseudo
      self.max_psuedo = newmax
      self.prop_max(newmax)


  def prop_absmin(self):
    """Propagate absolute time minimum from the given point to any descendants."""
    dlist = self.descendants
    xdlist = self.xdescendants

    # Propagate only to first in chain descendant - since it is recursive it will
    # get the rest of the chain anyway
    if dlist:
      ditem = dlist[0]
      assert isinstance(ditem, TimeLink)
      ditem.prop_min_to_point()
    
    # Propagate to all x-descendants
    for xitem in xdlist:
      assert isinstance(xitem, TimeLink)
      xitem.prop_min_to_point()


  def prop_absmax(self, oldabs):
    """Propagate absolute time maximum from the given point to any ancestors."""
    alist = self.ancestors
    xalist = self.xancestors

    # Propagate only to first in chain ancestor - since it is recursive it will
    # get the rest of the chain anyway
    if alist:
      aitem = alist[0]
      assert isinstance(aitem, TimeLink)
      aitem.prop_max_to_point(oldabs)
    
    # Propagate to all x-ancestors
    for xitem in xalist:
      assert isinstance(xitem, TimeLink)
      xitem.prop_max_to_point(oldabs)


  def update_absolute_min(self, abs):
    """Add a new absolute minimum time to this point."""
    assert isinstance(abs, AbsTime)
    max = self.absolute_max
    oldabs = self.absolute_min
    newabs = oldabs.merge_abs_min(abs, max)
    if not oldabs == newabs:
      self.absolute_min = newabs
      self.prop_absmin()


  def update_absolute_max(self, abs):
    """Add a new absolute maximum time to this point."""
    assert isinstance(abs, AbsTime)
    min = self.absolute_min
    oldabs = self.absolute_max
    newabs = oldabs.merge_abs_max(abs, min)
    if not oldabs == newabs:
      self.absolute_max = newabs
      self.prop_absmax(oldabs)


  def duration_between(self, tp):
    """Determine the duration between this and another point based on their absolute times."""
    assert isinstance(tp, TimePoint)
    min1 = self.absolute_min
    max1 = self.absolute_max
    min2 = tp.absolute_min
    max2 = tp.absolute_max
    return (max1.calc_duration_min(min2), min1.calc_duration_max(max2))


  def compare_absolute_times(self, tp):
    """Return the relation between this point and `tp` based on their absolute times."""
    assert isinstance(tp, TimePoint)
    absmin1 = self.absolute_min
    absmax1 = self.absolute_max
    absmin2 = tp.absolute_min
    absmax2 = tp.absolute_max
    test1 = absmax2.compare(absmin1)
    test2 = absmax1.compare(absmin2)
    test3 = absmin1.compare(absmin2)
    test4 = absmax1.compare(absmax2)

    # If max of self is before min of tp, then self is before tp
    if test_point_answer(PRED_BEFORE, test2):
      return PRED_BEFORE if test2 in PREDS_EQUIV else test2
    # If max of tp is before min of self, then self is after tp
    elif test_point_answer(PRED_BEFORE, test1):
      return PRED_AFTER if test1 in PREDS_EQUIV+[PRED_BEFORE] else f'{PRED_AFTER}-{1}'
    # If min of self = min of tp and max of self = max of tp, then they are equal
    elif test_point_answer(PRED_EQUAL, test3) and test_point_answer(PRED_EQUAL, test4):
      return PRED_SAME_TIME
    # Otherwise there is no way to tell using absolute times
    else:
      return PRED_UNKNOWN


  def __hash__(self):
    return hash(self.name)
  

  def __eq__(self, other):
    assert isinstance(other, TimePoint)
    return self.chain == other.chain and self.pseudo == other.pseudo
  

  def format(self, verbose=False, lvl=0):
    parts = []
    parts.append(f'{indent(lvl)}Node {self.name}')
    parts.append(f'{indent(lvl)}Chain {self.chain}')
    parts.append(f'{indent(lvl)}Pseudo {self.pseudo}')
    parts.append(f'{indent(lvl)}Min-pseudo {self.min_pseudo}')
    parts.append(f'{indent(lvl)}Max-pseudo {self.max_pseudo}')
    absmin = 'unknown' if self.absolute_min is None else self.absolute_min
    absmax = 'unknown' if self.absolute_max is None else self.absolute_max
    parts.append(f'{indent(lvl)}Absolute-min {absmin}')
    parts.append(f'{indent(lvl)}Absolute-max {absmax}')
    if verbose:
      if self.ancestors:
        parts.append(f'{indent(lvl)}Ancestors')
        parts.append(self.ancestors.format(node='from', lvl=lvl+1))
      if self.descendants:
        parts.append(f'{indent(lvl)}Descendants')
        parts.append(self.descendants.format(node='to', lvl=lvl+1))
      if self.xancestors:
        parts.append(f'{indent(lvl)}XAncestors')
        parts.append(self.xancestors.format(node='from', lvl=lvl+1))
      if self.xdescendants:
        parts.append(f'{indent(lvl)}XDescendants')
        parts.append(self.xdescendants.format(node='to', lvl=lvl+1))
      if self.alternate_names:
        parts.append(f'{indent(lvl)}Alternate-names')
        parts.append('\n'.join([f'{indent(lvl+1)}{n}' for n in self.alternate_names]))
    return '\n'.join(parts)


  def __str__(self):
    return self.format()



# ``````````````````````````````````````
# TimeLink
# ``````````````````````````````````````



class TimeLink:
  """A link between two time points.
  
  Attributes
  ----------
  from_tp : TimePoint
    Time point link is from.
  to_tp : TimePoint
    Time point link is to.
  strict : bool
    Indicates strictness.
  duration_min : float
    Minimum duration between `to` and `from` points.
  duration_max : float
    Maximum duration between `to` and `from` points.

  Parameters
  ----------
  from_tp : TimePoint, optional
  to_tp : TimePoint, optional
  strict : bool, default=False
  """

  def __init__(self, from_tp=None, to_tp=None, strict=False):
    assert ((isinstance(from_tp, TimePoint) or from_tp is None) and
            (isinstance(to_tp, TimePoint) or to_tp is None) and
            isinstance(strict, bool))
    self.from_tp = from_tp
    self.to_tp = to_tp
    self.strict = strict
    self.duration_min = 0
    self.duration_max = float('inf')


  def from_chain_number(self):
    return self.from_tp.chain.chain_number if self.from_tp else None
  

  def from_pseudo(self):
    return self.from_tp.pseudo if self.from_tp else None
  

  def to_chain_number(self):
    return self.to_tp.chain.chain_number if self.to_tp else None
  

  def to_pseudo(self):
    return self.to_tp.pseudo if self.to_tp else None
  

  def prop_min_to_point(self):
    """Propagate the minimum absolute time to the next descendant (the from point of this link)."""
    pt1 = self.from_tp
    pt2 = self.to_tp
    pt1abs = pt1.absolute_min
    pt1max = pt1.absolute_max
    pt2abs = pt2.absolute_min
    max = pt2.absolute_max
    durmin = self.duration_min
    durabs = pt1max.calc_duration_min(pt2abs)
    usedur = duration_min(durmin, durabs)

    newabs = pt1abs.re_calc_abs_min(pt2abs, max, usedur)
    if not newabs == pt2abs:
      pt2.absolute_min = newabs
      pt2.prop_absmin()


  def prop_max_to_point(self, oldabs):
    """Propagate the maximum absolute time to the previous ancestor (the to point of this link)."""
    assert isinstance(oldabs, AbsTime)
    pt1 = self.to_tp
    pt2 = self.from_tp
    pt1abs = pt1.absolute_max
    pt2min = pt2.absolute_min
    pt2abs = pt2.absolute_max
    durmin = self.duration_min
    durabs = oldabs.calc_duration_min(pt2min)
    usedur = duration_min(durmin, durabs)

    newabs = pt1abs.re_calc_abs_max(pt2abs, pt2min, usedur)
    if not newabs == pt2abs:
      pt2.absolute_max = newabs
      pt2.prop_absmax()


  def calc_duration(self):
    """Calculate the duration on a link, using both the stored duration information and absolute times."""
    tp1 = self.from_tp
    tp2 = self.to_tp
    absdur = tp1.duration_between(tp2)
    dmin = self.duration_min
    dmax = self.duration_max
    return get_best_duration(absdur, (dmin, dmax))


  def update_duration_min(self, d):
    """Add a minimum duration to this link and propagate absolute time if necessary."""
    assert type(d) in [int, float]
    if (d > 0 and not self.strict) or (not self.duration_min or d > self.duration_min):
      tp1 = self.from_tp
      tp2 = self.to_tp
      if d > 0 and not self.strict:
        self.strict = True
        if tp1.on_same_chain(tp2):
          tp1.add_strictness(tp2)
      if not self.duration_min or d > self.duration_min:
        self.duration_min = d
        tp1.update_absolute_max(tp2.absolute_max.calc_sub_dur(d))
        tp2.update_absolute_min(tp1.absolute_min.calc_add_dur(d))


  def update_duration_max(self, d):
    """Add a maximum duration to this link."""
    assert type(d) in [int, float]
    if not self.duration_max or d < self.duration_max:
      self.duration_max = d


  def __eq__(self, other):
    assert isinstance(other, TimeLink)
    return (self.from_chain_number() == other.from_chain_number() and
            self.from_pseudo() == other.from_pseudo() and
            self.to_chain_number() == other.to_chain_number() and
            self.to_pseudo() == other.to_pseudo())
  

  def format(self, node='both', lvl=0):
    if node == 'to':
      return f'{indent(lvl)}{self.to_tp.name}'
    elif node == 'from':
      return f'{indent(lvl)}{self.from_tp.name}'
    else:
      return f'{indent(lvl)}{self.from_tp.name} -> {self.to_tp.name}'
    

  def __str__(self):
    return self.format()



# ``````````````````````````````````````
# TimeLinkList
# ``````````````````````````````````````



class TimeLinkList(UserList):
  """A list of time links (a wrapper around a basic Python list)."""

  def add(self, item):
    """Insert `item` at the appropriate place in the list.
    
    The lists of links are ordered from chain, from psuedo, to chain, to psuedo. If an item
    is already in the list but the strictness is different, the most strict value is used for the link.
    """
    def test_insert(llist, item):
      if not llist:
        return True
      lk = llist[0]
      assert isinstance(lk, TimeLink) and isinstance(item, TimeLink)
      return (lk.from_chain_number() > item.from_chain_number()
            or (lk.from_chain_number() == item.from_chain_number()
                and (lk.from_pseudo() > item.from_pseudo()
                      or (lk.from_pseudo() == item.from_pseudo()
                          and (lk.to_chain_number() > item.to_chain_number()
                              or (lk.to_chain_number() == item.to_chain_number()
                                  and lk.to_pseudo() >= item.to_pseudo()))))))
    
    def ins_here(llist, item):
      lk = llist[0]
      assert isinstance(lk, TimeLink) and isinstance(item, TimeLink)
      if lk == item:
        if item.strict:
          lk.strict = True
        return llist
      else:
        return [item] + llist
      
    def ins_rec(llist, item):
      if not llist:
        return [item]
      elif test_insert(llist, item):
        return ins_here(llist, item)
      else:
        return [llist[0]] + ins_rec(llist[1:], item)
    
    self.data = ins_rec(self.data, item)
    return self
  

  def remove(self, item):
    """Remove `item` from the list if it exists in the list."""
    if item in self.data:
      self.data.remove(item)

  
  def format(self, node='both', lvl=0):
    return '\n'.join([link.format(node=node, lvl=lvl) for link in self.data])


  def __str__(self):
    return self.format()
  


# ``````````````````````````````````````
# MetaNode
# ``````````````````````````````````````

  

class MetaNode:
  """A node in the metagraph connecting time chains.
  
  Attributes
  ----------
  chain_number : int
    The chain number of this metanode.
  first : TimePoint
    The first time point in the chain for this metanode.
  connections : TimeLinkList
    All cross-chain links.

  Parameters
  ----------
  chain_number : int
  first : TimePoint, optional
  connections : TimeLinkList, optional
  """

  def __init__(self, chain_number, first=None, connections=TimeLinkList()):
    assert (isinstance(chain_number, int) and
            (isinstance(first, TimePoint) or first is None) and
            isinstance(connections, TimeLinkList))
    self.chain_number = chain_number
    self.first = first
    self.connections = connections


  def renumber(self):
    """Renumber the pseudo times in the chain.
    
    Notes
    -----
    Renumbering requires only that first descendant be used, as they are
    ordered, and if there is more than one, it means there are transitive edges 
    and they will be handled later anyway.
    """
    def renumber_next(last, dlist):
      assert isinstance(last, TimePoint) and isinstance(dlist, TimeLinkList)
      if dlist:
        ditem = dlist[0]
        assert isinstance(ditem, TimeLink)
        p = ditem.to_tp
        p.pseudo = last.pseudo_after()
        renumber_next(p, p.descendants)

    f = self.first
    f.pseudo = PSEUDO_INIT
    renumber_next(f, f.descendants)

  
  def __str__(self):
    return str(self.chain_number)



# ``````````````````````````````````````
# EventPoint
# ``````````````````````````````````````



class EventPoint:
  """A node representing an event (i.e., an interval with some start and end time points).
  
  Attributes
  ----------
  name : str
    The symbol denoting the event.
  start : str
    The start time point name.
  end : str
    The end time point name.

  Parameters
  ----------
  name : str
  start : str, optional
  end : str, optional
  """

  def __init__(self, name, start=None, end=None):
    assert (isinstance(name, str) and
            (isinstance(start, str) or start is None) and
            (isinstance(end, str) or end is None))
    self.name = name
    self.start = start if start else name+'start'
    self.end = end if end else name+'end'



# ``````````````````````````````````````
# TimeGraph
# ``````````````````````````````````````



class TimeGraph:
  """A timegraph structure.
  
  Attributes
  ----------
  chain_count : int
    An index marking the number of chains in the timegraph.
  timegraph : dict[str, TimePoint]
    A hash table of time points constituting the timegraph.
  metagraph : dict[int, MetaNode]
    A hash table of meta nodes.
  events : dict[str, EventPoint]
    A hash table of event nodes.
  rel_table : dict[str, str]
    A temporary storage of relations used in search algorithms.
  """

  def __init__(self):
    self.chain_count = 0
    self.timegraph = {}
    self.metagraph = {}
    self.events = {}
    self.rel_table = {}


  def newchain(self):
    """Create a new chain for the next available chain number and update the meta graph.
    
    Returns
    -------
    MetaNode
      The meta node corresponding to the new chain.
    """
    node = MetaNode(self.chain_count)
    self.metagraph[self.chain_count] = node
    self.chain_count += 1
    return node
  

  def time_point(self, name):
    """Return the time point corresponding to `name` if there is one, otherwise None."""
    assert isinstance(name, str)
    return self.timegraph[name] if name in self.timegraph else None
  

  def time_chain(self, chain_number):
    """Return the meta node corresponding to `chain_number` if there is one, otherwise None."""
    assert isinstance(chain_number, int)
    return self.metagraph[chain_number] if chain_number in self.metagraph else None
  

  def event_point(self, name):
    """Return the event point corresponding to `name`, if there is one, otherwise None."""
    assert isinstance(name, str)
    return self.events[name] if name in self.events else None
  

  def is_event(self, name):
    """Check whether `name` is a registered event point."""
    return isinstance(name, str) and name in self.events
  

  def get_start(self, a):
    """Get the start of a given concept.
    
    `a` is either an event, absolute time, or time point. In the first two
    cases, return the start time point and the absolute time itself, respectively. Otherwise,
    just return the time point.
    """
    if not a:
      return None
    elif isinstance(a, EventPoint):
      return self.time_point(a.start)
    elif isinstance(a, AbsTime):
      return a
    elif isinstance(a, TimePoint):
      return a
    else:
      return None
    

  def get_end(self, a):
    """Get the end of a given concept.
    
    `a` is either an event, absolute time, or time point. In the first two
    cases, return the end time point and the absolute time itself, respectively. Otherwise,
    just return the time point.
    """
    if not a:
      return None
    elif isinstance(a, EventPoint):
      return self.time_point(a.end)
    elif isinstance(a, AbsTime):
      return a
    elif isinstance(a, TimePoint):
      return a
    else:
      return None
  

  def add_meta_link(self, timelink):
    """Add a link to the meta graph for the appropriate chain."""
    assert isinstance(timelink, TimeLink)
    if not timelink.from_chain_number() == timelink.to_chain_number():
      mn = self.time_chain(timelink.from_chain_number())
      if mn:
        mn.connections.add(timelink)


  def remove_meta_link(self, timelink):
    """Remove a link from the meta graph."""
    assert isinstance(timelink, TimeLink)
    if not timelink.from_chain_number() == timelink.to_chain_number():
      mn = self.time_chain(timelink.from_chain_number())
      if mn:
        mn.connections.remove(timelink)


  def add_link(self, tp1, tp2, strict12):
    """Add a link between `tp1` and `tp2` with the appropriate strictness.
    
    If the two points are on different chains, a meta link is also added.
    """
    assert isinstance(tp1, TimePoint) and isinstance(tp2, TimePoint) and isinstance(strict12, int)
    if not tp1 == tp2:
      tl = TimeLink(from_tp=tp1, to_tp=tp2, strict=strict_p(strict12))
      if tp1.chain == tp2.chain:
        tp1.add_descendant_link(tl)
        tp2.add_ancestor_link(tl)
      else:
        tp1.add_xdescendant_link(tl)
        tp2.add_xancestor_link(tl)
        self.add_meta_link(tl)
      return tl
    

  def remove_link(self, timelink, linklist):
    """Remove `timelink` from `linklist`, as well as removing the meta-link if there is one."""
    assert isinstance(timelink, TimeLink) and isinstance(linklist, TimeLinkList)
    self.remove_meta_link(timelink)
    linklist.remove(timelink)


  def update_links(self, tp1, tp2, type):
    """Update the links of `type` from `tp1` to `tp2`, where `type` is "descendants", "ancestors", "xdescendants", or "xancestors".
    
    If `type` is "(x)descendants", for each link in `tp1`'s (x)descendants list, the "to" point ancestor list
    has this link removed, and then the link is added using `tp2` as the ancestor.

    If `type` is "(x)ascendants", for each link in `tp1`'s (x)ancestors list, the "from" point descendant list
    has this link removed, and then the link is added using `tp2` as the descendant.
    """
    assert isinstance(tp1, TimePoint) and isinstance(tp2, TimePoint)
    if type not in POINT_LINK_PAIRS.keys():
      raise Exception('Invalid type argument')
    
    linklist = getattr(tp1, type)
    for link in linklist:
      assert isinstance(link, TimeLink)
      if 'descendant' in type:
        tp = link.to_tp
      else:
        tp = link.from_tp
      durmin = link.duration_min
      durmax = link.duration_max
      self.remove_link(link, getattr(tp, POINT_LINK_PAIRS[type]))
      if 'descendant' in type:
        self.add_link(tp2, tp, link.strict)
        self.new_duration_min(tp2, tp, durmin)
        self.new_duration_max(tp2, tp, durmax)
      else:
        self.add_link(tp, tp2, link.strict)
        self.new_duration_min(tp, tp2, durmin)
        self.new_duration_max(tp, tp2, durmax)


  def find_link(self, tp1, tp2):
    """Find the link between `tp1`, and `tp2`, adding a link if none exists."""
    assert isinstance(tp1, TimePoint) and isinstance(tp2, TimePoint)
    chain2 = tp2.chain
    pseudo2 = tp2.pseudo
    if tp1.on_same_chain(tp2):
      dlist = tp1.descendants
    else:
      dlist = tp1.xdescendants
    link = None
    for item in dlist:
      assert isinstance(item, TimeLink)
      if item.to_chain_number() == chain2.chain_number and item.to_pseudo() == pseudo2:
        link = item
        break
    # Create link if it doesn't exist
    if link is None:
      link = self.add_link(tp1, tp2, 1)
    return link


  def copy_links(self, tp1, tp2):
    """Copy all links for `tp1` to `tp2`.
    
    Ensures that only links with points on the same chain go into the new in-chain lists,
    and only those with different chains go on the cross-chain lists.
    """
    assert isinstance(tp1, TimePoint) and isinstance(tp2, TimePoint)
    self.update_links(tp1, tp2, 'ancestors')
    self.update_links(tp1, tp2, 'xancestors')
    self.update_links(tp1, tp2, 'descendants')
    self.update_links(tp1, tp2, 'xdescendants')


  def add_single(self, tpname):
    """Add a single point to the net on a new chain."""
    assert isinstance(tpname, str)
    tp = TimePoint(tpname, chain=self.newchain())
    self.timegraph[tpname] = tp
    tp.update_first()
    return tp
  

  def add_absolute_min(self, t, abs):
    """Add an absolute minimum time to `t` (creating the point if it doesn't exist)."""
    assert type(t) in [str, TimePoint] and isinstance(abs, AbsTime)
    if isinstance(t, str):
      tp = self.time_point(t)
      if tp is None:
        tp = self.add_single(t)
    else:
      tp = t
    tp.update_absolute_min(abs)


  def add_absolute_max(self, t, abs):
    """Add an absolute maximum time to `t` (creating the point if it doesn't exist)."""
    assert type(t) in [str, TimePoint] and isinstance(abs, AbsTime)
    if isinstance(t, str):
      tp = self.time_point(t)
      if tp is None:
        tp = self.add_single(t)
    else:
      tp = t
    tp.update_absolute_max(abs)

  
  def new_duration_min(self, tp1, tp2, d):
    """Create a duration minimum between `tp1` and `tp2`."""
    assert isinstance(tp1, TimePoint) and isinstance(tp2, TimePoint) and type(d) in [int, float]
    link = self.find_link(tp1, tp2)
    link.update_duration_min(d)


  def add_duration_min(self, tpname1, tpname2, d):
    """Add a duration minimum between `tpname1` and `tpname2`."""
    assert isinstance(tpname1, str) and isinstance(tpname2, str) and type(d) in [int, float]
    if tpname1 not in self.timegraph or tpname2 not in self.timegraph:
      raise Exception(f'One of {tpname1} or {tpname2} does not exist in the timegraph.')
    tp1 = self.timegraph[tpname1]
    tp2 = self.timegraph[tpname2]
    self.new_duration_min(tp1, tp2, d)


  def new_duration_max(self, tp1, tp2, d):
    """Create a duration maximum between `tp1` and `tp2`."""
    assert isinstance(tp1, TimePoint) and isinstance(tp2, TimePoint) and type(d) in [int, float]
    link = self.find_link(tp1, tp2)
    link.update_duration_max(d)


  def add_duration_max(self, tpname1, tpname2, d):
    """Add a duration maximum between `tpname1` and `tpname2`."""
    assert isinstance(tpname1, str) and isinstance(tpname2, str) and type(d) in [int, float]
    if tpname1 not in self.timegraph or tpname2 not in self.timegraph:
      raise Exception(f'One of {tpname1} or {tpname2} does not exist in the timegraph.')
    tp1 = self.timegraph[tpname1]
    tp2 = self.timegraph[tpname2]
    self.new_duration_max(tp1, tp2, d)


  def search_meta(self, tp1, tp2, already, sofar):
    """Search for a path from `tp1` to `tp2` in the metagraph.
    
    Returns ``None`` if no path, ``before-1`` if a strict path, and
    ``before`` if a non-strict path.

    Notes
    -----
    Any path cannot go through any chain in `already`.
    
    `sofar` is the strictness value so far in the search.
    """
    assert isinstance(tp1, TimePoint) and isinstance(tp2, TimePoint)
    chain1 = tp1.chain
    chain2 = tp2.chain
    xlist = None
    res = None
    newsofar = None
    saveres = None

    if tp1.name in self.rel_table:
      return self.rel_table[tp1.name]

    if chain1:
      xlist = chain1.connections

    # For each connection that the chain of tp1 has to another chain:
    if not res and xlist:
      for item in xlist:
        assert isinstance(item, TimeLink)
        frompt = item.from_tp
        topt = item.to_tp
        path1 = tp1.find_pseudo(frompt)
        newchainno = item.to_chain_number()

        # See if this link is usable (must be before or equal tp1)
        if test_point_answer(PRED_BEFORE, path1):
          newsofar = calc_path(sofar, path1, item)

          # If we got the end chain, see if this ends the search
          if newchainno == chain2.chain_number:
            res = check_chain(newsofar, tp2, item)
          # Otherwise continue search if this chain hasn't been searched yet
          elif not newchainno in already:
            res = self.search_meta(topt, tp2, [newchainno]+already, newsofar)

          # If we have an answer, return it, otherwise continue with next connection
          if res and res != PRED_UNKNOWN:
            # If we have a strict path return it; if nonstrict, save it and continue search
            if res == f'{PRED_BEFORE}-{1}':
              return res
            else:
              saveres = res
              res = None

    # If no answer, see if we saved one earlier
    if not res or res == PRED_UNKNOWN:
      res = saveres
    res = PRED_UNKNOWN if not res else res
    if res:
      self.rel_table[tp1.name] = res
    res = None if res == PRED_UNKNOWN else res
    return res
  

  def search_path(self, tp1, tp2):
    """Return ``None`` if there is no path from `tp1` to `tp2`; ``before-1`` or ``before`` if there is."""
    assert isinstance(tp1, TimePoint) and isinstance(tp2, TimePoint)
    self.rel_table = {}
    res = self.search_meta(tp1, tp2, [tp1.chain.chain_number], None)
    self.rel_table = {}
    return res
  

  def find_reln(self, tp1, tp2, effort=DEFAULT_EFFORT):
    """Find the most strict relation that holds between `tp1` and `tp2`.
    
    `effort` indicates how hard it should search (0 or 1).
    """
    assert isinstance(tp1, TimePoint) and isinstance(tp2, TimePoint)
    result = PRED_UNKNOWN
    backup = PRED_UNKNOWN

    # If on the same chain, compare pseudo times
    if tp1 == tp2:
      result = PRED_SAME_TIME
    if tp1.on_same_chain(tp2):
      result = tp1.find_pseudo(tp2)

    # If no answer yet, compare absolute times
    if result == PRED_UNKNOWN:
      result = tp1.compare_absolute_times(tp2)

      # If the result is equal, there may still be a path indicating
      # a temporal order (<= or >=). Set result unknown so that this
      # will be pursued, but save equal result just in case
      if result in PREDS_EQUIV and effort > 0:
        backup = result
        result = PRED_UNKNOWN

    # If no answer yet, and effort indicates ok to continue, search
    # for path from tp1 to tp2, or tp2 to tp1
    if result == PRED_UNKNOWN and effort > 0:
      path1 = self.search_path(tp1, tp2)
      if path1:
        result = path1
      else:
        path2 = inverse_reln(self.search_path(tp2, tp1))
        if path2:
          result = path2
        else:
          result = PRED_UNKNOWN

    # If absolute time comparisons gave equal and the search gave no
    # more information, use the equal
    if result == PRED_UNKNOWN and not backup == PRED_UNKNOWN:
      result = backup

    return result
  

  def find_point(self, t1, t2, effort=DEFAULT_EFFORT):
    """Find the most strict relationship that holds between `t1` and `t2`, which may be either absolute times or points.
    
    `effort` indicates how hard it should search (0 or 1).
    """
    assert type(t1) in [TimePoint, AbsTime] and type(t2) in [TimePoint, AbsTime]
    result = PRED_UNKNOWN
    if t1 == t2:
      result = PRED_SAME_TIME
    elif isinstance(t1, AbsTime) or isinstance(t2, AbsTime):
      result = self.find_absolute(t1, t2, effort=effort)
    elif t1 and t2:
      result = self.find_reln(t1, t2, effort=effort)
    return result
  

  def abs_relation(self, abs, tp):
    """Determine the relation between an absolute time `abs` and a point `tp`."""
    assert isinstance(abs, AbsTime) and (isinstance(tp, TimePoint) or tp is None)
    if not tp:
      return PRED_UNKNOWN
    res1 = abs.compare(tp.absolute_min)
    res2 = abs.compare(tp.absolute_max)
    if test_point_answer(PRED_EQUAL, res1) and test_point_answer(PRED_EQUAL, res2):
      return PRED_SAME_TIME
    elif test_point_answer(PRED_BEFORE, res1):
      return PRED_BEFORE if res1 in PREDS_EQUIV else res1
    elif test_point_answer(PRED_AFTER, res2):
      return PRED_AFTER if res2 in PREDS_EQUIV else res2
    else:
      return PRED_UNKNOWN
  

  def find_absolute(self, a1, a2, effort=DEFAULT_EFFORT):
    """Return the relationship between `a1` and `a2`, where one is an absolute time.
    
    `effort` indicates how hard it should search (0 or 1).
    """
    if isinstance(a1, AbsTime):
      if isinstance(a2, AbsTime):
        return a1.compare(a2)
      elif isinstance(a2, TimePoint):
        return self.abs_relation(a1, a2)
    elif isinstance(a1, TimePoint):
      if isinstance(a2, AbsTime):
        return inverse_reln(self.abs_relation(a2, a1))
      elif isinstance(a2, TimePoint):
        return self.find_point(a1, a2, effort=effort)
    return PRED_UNKNOWN
  

  def find_absolute_reln(self, a1, a2, effort=DEFAULT_EFFORT):
    """Return the relationship between `a1` and `a2`, which may be events with absolute times.
    
    `effort` indicates how hard it should search (0 or 1).
    """
    if isinstance(a1, AbsTime) and isinstance(a2, AbsTime):
      return self.find_absolute(a1, a2, effort=effort)
    a1start = self.get_start(a1)
    a2start = self.get_start(a2)
    a1end = self.get_end(a1)
    a2end = self.get_end(a2)
    res1 = self.find_absolute(a1start, a2end, effort=effort)
    res2 = self.find_absolute(a1end, a2start, effort=effort)

    # If start and end are equal, equal
    if test_point_answer(PRED_EQUAL, res1) and test_point_answer(PRED_EQUAL, res2):
      return PRED_SAME_TIME
    
    # If start of 1 after end of 2, after
    elif test_point_answer(PRED_AFTER, res1):
      return PRED_AFTER if res1 in PREDS_EQUIV else res1
    
    # If end of 1 before start of 2, before
    elif test_point_answer(PRED_BEFORE, res2):
      return PRED_BEFORE if res2 in PREDS_EQUIV else res2
    
    return PRED_UNKNOWN
  

  def search_for_duration(self, tp1, tp2, dur, already):
    """Return minimum and maximum durations if path between `tp1` and `tp2`; None otherwise."""
    assert isinstance(tp1, TimePoint) and isinstance(tp2, TimePoint)
    desclist = tp1.descendants + tp1.xdescendants
    usedur = (0, float('inf'))
    curdur = None

    for item in desclist:
      assert isinstance(item, TimeLink)
      topt = item.to_tp
      linkdur = item.calc_duration()
      # Make sure we don't loop
      if topt.name not in already:
        curdur = combine_durations(dur, linkdur) if dur else linkdur
        # If this is the end point we're looking for, get the best duration so far
        if topt == tp2:
          usedur = get_best_duration(usedur, curdur)
        # Otherwise add this link and continue
        else:
          usedur = get_best_duration(usedur, self.search_for_duration(topt, tp2, curdur, already+[topt.name]))
  
    return usedur
  

  def calc_duration(self, tp1, tp2, effort=DEFAULT_EFFORT):
    """Determine the duration between two points.
    
    If either point doesn't exist, returns unknown. If they exist, it first
    determines the duration based on their absolute times. If the min is
    greater than the max, the points are reversed. If we have a range, and
    the effort level `effort` (0 or 1) indicates to continue trying,
    ``search_for_duration`` is called to determine the best duration along
    any path. The best between this and the absolute time duration is returned.
    """
    assert (isinstance(tp1, TimePoint) or tp1 is None) and (isinstance(tp2, TimePoint) or tp2 is None)
    if not tp1 or not tp2:
      return (0, float('inf'))
    durans = tp1.duration_between(tp2)
    durmin, durmax = durans
    if (not durmin or durmax == float('inf') or not durmax) and effort > 0:
      dursearch = self.search_for_duration(tp1, tp2, None, [tp1.name])
      durans = get_best_duration(durans, dursearch)
    durmin, durmax = durans
    durmin = 0 if not durmin else durmin
    durmax = float('inf') if not durmax else durmax
    return (durmin, durmax)
  

  def find_relation(self, a1, a2, effort=DEFAULT_EFFORT):
    """Return the most strict relation found between `a1` and `a2`, which may be either events or points.
    
    It determines relationships between the starts, ends, and start of one, end of the other, and uses
    those results to determine the actual relation.

    `effort` indicates how hard it should search (0 or 1).
    """
    if a1 == a2:
      return PRED_SAME_TIME
    if not type(a1) in [EventPoint, TimePoint] or not type(a2) in [EventPoint, TimePoint]:
      return PRED_UNKNOWN
    
    a1start = self.get_start(a1)
    a1end = self.get_end(a1)
    a2start = self.get_start(a2)
    a2end = self.get_end(a2)
    result = PRED_UNKNOWN
    isa1event = isinstance(a1, EventPoint)
    isa2event = isinstance(a2, EventPoint)
    e1s2 = self.find_point(a1end, a2start, effort=effort)

    # If end of a1 is before the start of a2, a1 is before a2
    # if a1 and a2 are both points, we just return the point relation
    # between the two and skip the rest of this function
    if test_point_answer(PRED_BEFORE, e1s2) or (not isa1event and not isa2event):
      if e1s2 in PREDS_EQUIV and (isa1event or isa2event):
        result = f'{PRED_BEFORE}-{0}'
      else:
        result = e1s2

    # If the start of a1 is after the end of a2, a1 is after a2
    if result == PRED_UNKNOWN and (isa1event or isa2event):
      s1e2 = self.find_point(a1start, a2end, effort=effort)
      if test_point_answer(PRED_AFTER, s1e2):
        if s1e2 in PREDS_EQUIV and (isa1event or isa2event):
          result = f'{PRED_AFTER}-{0}'
        else:
          result = s1e2

    # If the start points are equal, and the end points are equal, a1 = a2
    if result == PRED_UNKNOWN and (isa1event or isa2event):
      s1s2 = self.find_point(a1start, a2start, effort=effort)
      e1e2 = self.find_point(a1end, a2end, effort=effort)
      if test_point_answer(PRED_EQUAL, s1s2) and test_point_answer(PRED_EQUAL, e1e2):
        result = PRED_SAME_TIME

    # All other relations require that at least one of the arguments be an event
    if result == PRED_UNKNOWN and (isa1event or isa2event):
      strict1 = 0 if s1s2 in PREDS_EQUIV else split_time_pred(s1s2)[1]
      strict2 = 0 if e1e2 in PREDS_EQUIV else split_time_pred(e1e2)[1]
      
      # If the start of the first is after the start of the second,
      # a1 is either during a2, or overlapped by it
      if test_point_answer(PRED_AFTER, s1s2):
        if test_point_answer(PRED_BEFORE, e1e2):
          result = build_pred(PRED_DURING, strict1=strict1, strict2=strict2)
        elif test_point_answer(PRED_AFTER, e1e2):
          result = build_pred(PRED_OVERLAPPED_BY, strict1=strict1, strict2=strict2)
      
      # If the start of the first is before the start of the second,
      # a1 either contains a2, or overlaps it
      if test_point_answer(PRED_BEFORE, s1s2):
        if test_point_answer(PRED_BEFORE, e1e2):
          result = build_pred(PRED_OVERLAPS, strict1=strict1, strict2=strict2)
        elif test_point_answer(PRED_AFTER, e1e2):
          result = build_pred(PRED_CONTAINS, strict1=strict1, strict2=strict2)

    return result
  

  def evaluate_absolute(self, a1, stem, a2, a3=None, s1=-1, s2=-1, effort=DEFAULT_EFFORT):
    """Determine the tests required to determine if a relation holds between points, where one is an absolute time.
    
    ``determine_split`` is used to get the relations needed between the points (only the first two are required - four
    are returned in some cases); the tests are then done, and if any returns with False or unknown, that is the result,
    otherwise True.
    """
    assert (type(a1) in [TimePoint, EventPoint, AbsTime] and isinstance(stem, str) and
            type(a2) in [TimePoint, EventPoint, AbsTime] and
            (type(a3) in [TimePoint, EventPoint, AbsTime] or a3 is None) and
            isinstance(s1, int) and isinstance(s2, int))
    predlist = determine_split(stem, s1, s2)
    preds = [build_pred(a[0], strict1=a[1]) for a in predlist]
    usepreds = preds[0:2]
    tps1 = self.get_start(a1)
    tpe1 = self.get_end(a1)
    if stem == PRED_BETWEEN:
      tp2 = self.get_end(a2)
      tp3 = self.get_start(a3)
      res1 = test_point_answer(usepreds[0], self.find_absolute(tps1, tp2, effort=effort))
      res2 = test_point_answer(usepreds[1], self.find_absolute(tpe1, tp3, effort=effort))
      return combine_test_results(res1, res2)
    else:
      tps2 = self.get_start(a2)
      tpe2 = self.get_end(a2)
      res1 = test_point_answer(usepreds[0], self.find_absolute(tps1, tps2, effort=effort))
      res2 = test_point_answer(usepreds[1], self.find_absolute(tpe1, tpe2, effort=effort))
      res12 = combine_test_results(res1, res2)
      # should also check during a3
      if a3 is None or not res12:
        return res12
      else:
        res3 = self.evaluate_absolute(a1, PRED_DURING, a3)
        return combine_test_results(res12, res3)
      

  def determine_tests(self, a1, stem, a2, a3=None, s1=-1, s2=-1):
    """Return a list of tests to be done to see if the given relation holds between the given points/events.
    
    It uses ``determine_split`` which returns the relations that must hold between the start points, end points,
    start of first/end of second, and start of second/end of first.
    """
    assert (type(a1) in [TimePoint, EventPoint] and isinstance(stem, str) and
            type(a2) in [TimePoint, EventPoint] and
            (type(a3) in [TimePoint, EventPoint] or a3 is None) and
            isinstance(s1, int) and isinstance(s2, int))
    predlist = determine_split(stem, s1, s2)
    preds = [build_pred(a[0], strict1=a[1]) for a in predlist]
    if stem == PRED_BETWEEN:
      a1start = self.get_start(a1)
      a1end = self.get_end(a1)
      a2end = self.get_end(a2)
      a3start = self.get_start(a3)
      endtest = build_pred(PRED_BEFORE, combine_strict(s1, s2))
      s1e2 = preds[0]
      e1s3 = preds[1]
      todolist = [(a1start, s1e2, a2end)]
      if isinstance(a1, EventPoint):
        todolist.append((a1end, e1s3, a3start))
      todolist.append((a2end, endtest, a3start))
      return todolist
    else:
      a1start = self.get_start(a1)
      a1end = self.get_end(a1)
      a2start = self.get_start(a2)
      a2end = self.get_end(a2)
      s1s2 = preds[0]
      e1e2 = preds[1]
      s1e2 = preds[2]
      e1s2 = preds[3]
      todolist = [(a1start, s1s2, a2start)]
      if isinstance(a1, EventPoint) or isinstance(a2, EventPoint) or stem in PREDS_CONTAINMENT:
        todolist.append((a1end, e1e2, a2end))
        todolist.append((a1start, s1e2, a2end))
        todolist.append((a1end, e1s2, a2start))
      if a3 is not None:
        todolist = todolist + self.determine_tests(a1, PRED_DURING, a3)
      return todolist
    

  def evaluate_point_relations(self, a1, stem, a2, a3=None, s1=-1, s2=-1, effort=DEFAULT_EFFORT):
    """Evaluate all tests for point/event relations."""
    assert (type(a1) in [TimePoint, EventPoint] and isinstance(stem, str) and
            type(a2) in [TimePoint, EventPoint] and
            (type(a3) in [TimePoint, EventPoint] or a3 is None) and
            isinstance(s1, int) and isinstance(s2, int))
    todo = self.determine_tests(a1, stem, a2, a3, s1, s2)
    res = True
    majorres = True

    for (tp1, pred, tp2) in todo:
      res = test_point_answer(pred, self.find_point(tp1, tp2, effort=effort))
      if res is False:
        return res
      elif res is None:
        majorres = None
    
    if res is False:
      return False
    elif majorres is None:
      return None
    else:
      return res
    

  def test_minimum_duration(self, dur, test):
    """Determine if the minimum duration in `dur` is at least `test` (either a min/max pair or a number)."""
    assert ((isinstance(dur, tuple) and len(dur) == 2 and type(dur[0]) in [int, float] and type(dur[1]) in [int, float]) and
            ((isinstance(test, tuple) and len(test) == 2 and type(test[0]) in [int, float] and type(test[1]) in [int, float]) or
             type(test) in [int, float]))
    testvalue = test if isinstance(test, tuple) else (test, test)
    testmin, testmax = testvalue
    dmin, dmax = dur
    if dmin is None or dmin == float('-inf'):
      return None
    elif dmin >= testmax:
      return True
    elif dmax is None or dmax == float('inf'):
      return None
    elif dmin == float('inf') or dmax == float('-inf') or dmin < testmin or dmax < testmin:
      return False
    else:
      return None
    

  def test_maximum_duration(self, dur, test):
    """Determine if the maximum duration in `dur` is at most `test` (either a min/max pair or a number)."""
    assert ((isinstance(dur, tuple) and len(dur) == 2 and type(dur[0]) in [int, float] and type(dur[1]) in [int, float]) and
            ((isinstance(test, tuple) and len(test) == 2 and type(test[0]) in [int, float] and type(test[1]) in [int, float]) or
             type(test) in [int, float]))
    testvalue = test if isinstance(test, tuple) else (test, test)
    testmin, testmax = testvalue
    dmin, dmax = dur
    if dmax is None or dmax == float('inf'):
      return None
    elif dmax <= testmin:
      return True
    elif dmin is None or dmin == float('-inf'):
      return None
    elif dmin == float('inf') or dmax == float('-inf') or dmin > testmax or dmax > testmax:
      return False
    else:
      return None


  def evaluate_durations(self, a1, reln, a2, testdur, effort=DEFAULT_EFFORT):
    """Try to determine if the given relation actually holds between `a1` and `a3` with duration `a3`.
    
    First determine the duration between them; if the duration comes back without giving any information,
    check to see if the opposite relation holds between the points. If so, the answer is False.
    """
    assert (type(a1) in [TimePoint, EventPoint] and isinstance(reln, str) and
            type(a2) in [TimePoint, EventPoint] and
            type(testdur) in [int, float])
    dur = None

    # determine duration in appropriate direction
    if reln in PREDS_CONSTRAINED_BEFORE:
      dur = self.calc_duration(self.get_end(a1), self.get_start(a2), effort=effort)
    elif reln in PREDS_CONSTRAINED_AFTER:
      dur = self.calc_duration(self.get_end(a2), self.get_start(a1), effort=effort)
    
    # if inconclusive result, check to see if opposite relation holds
    if dur is None or dur == (float('-inf'), float('inf')):
      if reln in PREDS_CONSTRAINED_BEFORE:
        res = self.evaluate_point_relations(a1, PRED_BEFORE, a2, strict1=1, effort=effort)
        return False if res is False else None
      elif reln in PREDS_CONSTRAINED_AFTER:
        res = self.evaluate_point_relations(a1, PRED_AFTER, a2, strict1=1, effort=effort)
        return False if res is False else None
      else:
        return None
    # otherwise, look at the duration returned
    else:
      if reln in [PRED_AT_LEAST_BEFORE, PRED_AT_LEAST_AFTER]:
        return self.test_minimum_duration(dur, testdur)
      elif reln in [PRED_AT_MOST_BEFORE, PRED_AT_MOST_AFTER]:
        return self.test_maximum_duration(dur, testdur)
      elif reln in [PRED_EXACTLY_BEFORE, PRED_EXACTLY_AFTER]:
        return combine_test_results(self.test_minimum_duration(dur, testdur),
                                    self.test_maximum_duration(dur, testdur))
      else:
        return None


  def evaluate_time(self, a1, reln, a2, a3=None, effort=DEFAULT_EFFORT, negated=False):
    """Evaluate a particular relation between two or three arguments."""
    assert (type(a1) in [TimePoint, EventPoint, AbsTime] and isinstance(reln, str) and
            type(a2) in [TimePoint, EventPoint, AbsTime] and
            (type(a3) in [TimePoint, EventPoint, AbsTime] or a3 is None))
    if negated:
      posans = self.evaluate_time(a1, reln, a2, a3, effort=effort)
      if posans is None:
        return None
      else:
        return not posans
        
    stem, s1, s2 = split_time_pred(reln)
    if isinstance(a1, AbsTime) or isinstance(a2, AbsTime) or (stem == PRED_BETWEEN and isinstance(a3, AbsTime)):
      return self.evaluate_absolute(a1, stem, a2, a3, s1, s2, effort=effort)
    elif reln in PREDS_CONSTRAINED_BEFORE + PREDS_CONSTRAINED_AFTER:
      return self.evaluate_durations(a1, reln, a2, a3, effort=effort) if type(a3) in [int, float] else None
    else:
      return self.evaluate_point_relations(a1, stem, a2, a3, s1, s2, effort=effort)
  

  def check_inconsistent(self, f, l, reln, effort=DEFAULT_EFFORT):
    """Return True if the two points would be inconsistent if the relation `reln` is added.
    
    Used to ensure that if evaluation came back with unknown (therefore ok to enter), the net
    remains consistent after the entry. For example, if a <= b and we add a >= b, evaluation is
    unknown, but to remain consistent, it must be a = b.
    """
    assert type(f) in [TimePoint, AbsTime] and type(l) in [TimePoint, AbsTime]
    oldreln = self.find_point(f, l, effort=effort)
    if reln == PRED_BEFORE:
      return oldreln in PREDS_EQUIV + [PRED_AFTER, f'{PRED_AFTER}-{0}', f'{PRED_BEFORE}-{0}']
    elif reln == PRED_AFTER:
      return oldreln in PREDS_EQUIV + [PRED_BEFORE, f'{PRED_BEFORE}-{0}', f'{PRED_AFTER}-{0}']
    else:
      return False
    

  def update_point(self, tpname, newtp):
    """Update the pointer for the point named `tpname` in the timegraph to `newtp`."""
    assert isinstance(tpname, str) and isinstance(newtp, TimePoint)
    newtp.alternate_names.add(tpname)
    self.timegraph[tpname] = newtp


  def merge_names(self, tp1, tp2):
    """Merge the names of `tp2` into `tp1`."""
    assert isinstance(tp1, TimePoint) and isinstance(tp2, TimePoint)
    for tpname in tp2.alternate_names:
      self.update_point(tpname, tp1)
    tp1.alternate_names = tp1.alternate_names.union(tp2.alternate_names)
    self.update_point(tp2.name, tp1)


  def collapse_nodes(self, tp1, tp2):
    """Collapses two nodes into one to make them equal.
    
    First copy all the link information from the second point to the first, then
    make the second point actually point to the first.
    """
    assert isinstance(tp1, TimePoint) and isinstance(tp2, TimePoint)
    self.copy_links(tp1, tp2)
    self.merge_names(tp1, tp2)


  def get_path(self, tp1, tp2):
    """Return a list containing all points in the same chain from `tp1` to `tp2`, inclusive."""
    assert isinstance(tp1, TimePoint) and isinstance(tp2, TimePoint)
    next = tp1.descendants[0].to_tp if tp1.descendants else None
    if tp1 == tp2:
      return [tp1]
    elif not next:
      raise Exception(f'No in-chain path exists between {tp1.name} and {tp2.name}.')
    else:
      return [tp1] + self.get_path(next, tp2)
    

  def collapse_chain(self, tp1, tp2):
    """Make two points on the same chain equal (all points between must be made equal as well)."""
    assert isinstance(tp1, TimePoint) and isinstance(tp2, TimePoint)
    min1 = tp1.min_pseudo
    min2 = tp2.min_pseudo
    max1 = tp1.max_pseudo
    max2 = tp2.max_pseudo
    absmin1 = tp1.absolute_min
    absmin2 = tp1.absolute_min
    
    for tpi in self.get_path(tp1, tp2)[1:]:
      self.collapse_nodes(tp1, tpi)

    # max and min must be most constrained of the points
    if min2 > float('-inf') and min2 > min1:
      tp1.min_pseudo = min2
      tp1.first_desc().prop_min(min2)
    if max2 < float('inf') and max2 < max1:
      tp1.max_pseudo = max2
      tp1.first_anc().prop_max(max2)

    # update absolute time minimum if necessary - no need to propagate
    # because propagation of min goes forward, and this would already
    # have been done. Max would have been propagated back originally
    # if max of tp2 were < max ot tp1
    if absmin2 and (not absmin1 or test_answer(PRED_AFTER, absmin2.compare(absmin1))):
      tp1.absolute_min = absmin2


  def collapse_xchain(self, tp1, tp2):
    """Make two time points on separate chains equal.
    
    It first checks to see if `tp2` is first on its chain, and if so, replaces
    the first by `tp2`'s first descendant. Any links `tp2` has are copied to `tp1`,
    and `tp2` is replaced by `tp1` in the time graph.
    """
    assert isinstance(tp1, TimePoint) and isinstance(tp2, TimePoint)
    absmin2 = tp2.absolute_min
    absmax2 = tp2.absolute_max

    tp2.check_first()
    self.copy_links(tp2, tp1)

    # copy absolute time
    tp1.update_absolute_min(absmin2)
    tp1.update_absolute_max(absmax2)

    self.merge_names(tp1, tp2)


  def add_equal(self, t1, tp2):
    """Make two points equal.
    
    `t1` is either a time point, or a name if no time point yet exists.
    `tp2` is the time point for the second point, which must already exist.
    """
    assert type(t1) in [str, TimePoint] and isinstance(tp2, TimePoint)
    # If t1 is new, just make it point to tp2
    if isinstance(t1, str) and not t1 in self.timegraph:
      self.update_point(t1, tp2)
    
    # Otherwise, we need to copy relevant info from tp1 to tp2
    else:
      tp1 = t1 if isinstance(t1, TimePoint) else self.time_point(t1)
      # check to make sure that these points could be equal; otherwise could get loops
      # TODO: this test only for those in same chain - should do consistency search for others
      if tp1.on_same_chain(tp2) and not tp1.possibly_equal(tp2):
        return
      # check if they are already equal - no need to do anything
      elif tp1 == tp2:
        return
      # if tp2 has not been replaced by any other point, copy its information to tp1 and replace
      else:
        if tp1.on_same_chain(tp2):
          self.collapse_chain(tp1, tp2)
        else:
          self.collapse_xchain(tp1, tp2)


  def add_before_same_chain(self, f, l, strictfl):
    """Set the chain of point `f` to be the same as `l`'s, and set its pseudo time to be before `l`'s."""
    assert isinstance(f, TimePoint) and isinstance(l, TimePoint) and isinstance(strictfl, int)
    f.chain = l.chain
    f.pseudo = l.pseudo_before()

    # if the arc between is strict, f's maximum is l, l's minimum is f, and this is propagated
    if strict_p(strictfl):
      f.max_pseudo = l.pseudo
      l.min_pseudo = f.pseudo
      l.prop_min(f.pseudo)
    # otherwise, f's maximum is l's maximum
    else:
      f.max_pseudo = l.max_pseudo

    f.update_first()
      

  def add_after_same_chain(self, l, f, strictfl):
    """Set the chain of point `l` to be the same as `f`'s, and set its pseudo time to be after `f`'s."""
    assert isinstance(l, TimePoint) and isinstance(f, TimePoint) and isinstance(strictfl, int)
    l.chain = f.chain
    l.pseudo = f.pseudo_after()

    # if the arc between is strict, l's minimum is f, f's maximum is l, and this is propagated
    if strict_p(strictfl):
      l.min_pseudo = f.pseudo
      f.max_pseudo = l.pseudo
      f.prop_max(l.pseudo)
    # otherwise, l's minimum is f's minimum
    else:
      l.min_pseudo = f.min_pseudo


  def add_between_same_chain(self, m, f, l, strictfm, strictml):
    """Set the chain of point `m` to be the same as `f` and `l`, and set its pseudo time to be between."""
    assert (isinstance(m, TimePoint) and isinstance(f, TimePoint) and isinstance(l, TimePoint) and
            isinstance(strictfm, int) and isinstance(strictml, int))
    m.chain = f.chain
    m.pseudo = f.pseudo_between(l)

    # set m's minimum
    # if the arc between f and m is strict, m's minimum is f, f's maximum is m, and this is propagated
    if strict_p(strictfm):
      m.min_pseudo = f.pseudo
      f.max_pseudo = m.pseudo
      f.prop_max(m.pseudo)
      l.prop_min(f.pseudo)
    # otherwise, m's minimum is f's minimum
    else:
      m.min_pseudo = f.min_pseudo

    # set m's maximum
    # if the arc between m and l is strict, m's maximum is l, l's minimum is m, and this is propagated
    if strict_p(strictml):
      m.max_pseudo = l.pseudo
      l.min_pseudo = m.pseudo
      l.prop_min(m.pseudo)
      f.prop_max(l.pseudo)
    # otherwise, m's maximum is l's maximum
    else:
      m.max_pseudo = l.max_pseudo


  def add_on_new_chain(self, tp):
    """Set the chain of `tp` to be a new chain, and set the first indicator for that new chain."""
    assert isinstance(tp, TimePoint)
    tp.chain = self.newchain()
    tp.pseudo = PSEUDO_INIT
    tp.update_first()


  def add_before(self, fname, lname, strict):
    """Add `fname` before `lname`.
    
    If `fname` doesn't exist, it is added on the same chain as `lname` if possible.
    Otherwise it starts a new chain. A link is added between them reflecting the strictness.
    """
    assert isinstance(fname, str) and isinstance(lname, str) and isinstance(strict, int)
    f = self.time_point(fname)
    l = self.time_point(lname)

    if l is None or not isinstance(l, TimePoint):
      raise Exception(f"Time point {lname} doesn't exist in timegraph.")
    
    # if first is new, create it
    if f is None:
      f = TimePoint(fname)
      self.update_point(fname, f)
      if l.first_in_chain():
        self.add_before_same_chain(f, l, strict)
      else:
        self.add_on_new_chain(f)
      
    # if they are on the same chain, adjust pseudo-times if necessary to reflect strictness
    if f and strict_p(strict) and f.on_same_chain(l):
      f.add_strictness(l)

    # add the link
    self.add_link(f, l, strict)

    # update absolute times
    f.update_absolute_max(l.absolute_max)
    l.update_absolute_min(f.absolute_min)


  def add_after(self, lname, fname, strict):
    """Add `lname` after `fname`.
    
    If `lname` doesn't exist, it is added to the same chain as `fname` if possible.
    Otherwise it starts a new chain. A link is added between them reflecting the strictness.
    """
    assert isinstance(lname, str) and isinstance(fname, str) and isinstance(strict, int)
    l = self.time_point(lname)
    f = self.time_point(fname)

    if f is None or not isinstance(f, TimePoint):
      raise Exception(f"Time point {fname} doesn't exist in timegraph.")
    
    # if last is new, create it
    if l is None:
      l = TimePoint(lname)
      self.update_point(lname, l)
      if f.last_in_chain():
        self.add_after_same_chain(l, f, strict)
      else:
        self.add_on_new_chain(l)

    # if they are on the same chain, adjust pseudo-times if necessary to reflect strictness
    if l and strict_p(strict) and f.on_same_chain(l):
      f.add_strictness(l)

    # add the link
    # TODO: should we check for an existing link before adding one?
    self.add_link(f, l, strict)

    # update absolute times
    l.update_absolute_min(f.absolute_min)
    f.update_absolute_max(l.absolute_max)


  def add_between(self, mname, fname, lname, strictfm, strictml):
    """Add `mname` between `fname` and `lname`.
    
    If `mname` doesn't exist, try to add it to the same chain as `fname` and/or `lname`
    to minimize chains. If this is not possible, a new chain is started. Links are created
    between first and middle, and middle and last, reflecting the strictness given.
    """
    assert (isinstance(mname, str) and isinstance(fname, str) and isinstance(lname, str) and
            isinstance(strictfm, int) and isinstance(strictml, int))
    m = self.time_point(mname)
    f = self.time_point(fname)
    l = self.time_point(lname)

    if f is None or not isinstance(f, TimePoint):
      raise Exception(f"Time point {fname} doesn't exist in timegraph.")   
    if l is None or not isinstance(l, TimePoint):
      raise Exception(f"Time point {lname} doesn't exist in timegraph.") 
    
    # if middle is new, create it, unless it's just being set equal to one of the other points
    if m is None:
      if strictfm == 0:
        self.add_equal(mname, f)
        m = f
      elif strictml == 0:
        self.add_equal(mname, l)
        m = l
      else:
        m = TimePoint(mname)
        self.update_point(mname, m)
        # if adjacent on same chain, add on same chain, else new chain
        if f.on_same_chain(l):
          if f.adjacent(l):
            self.add_between_same_chain(m, f, l, strictfm, strictml)
          else:
            self.add_on_new_chain(m)
        # if first is at end of chain, add middle after it
        elif f.last_in_chain():
          self.add_after_same_chain(m, f, strictfm)
        # if last is at beginning of its chain, add middle before it
        elif l.first_in_chain():
          self.add_before_same_chain(m, l, strictml)
        # otherwise add it on a new chain
        else:
          self.add_on_new_chain(m)

    # if strictness indicates that first = middle, and middle wasn't just
    # set to first above, make them equal; otherwise add the link between first/middle
    if strictfm == 0:
      if f != m:
        self.add_equal(m, f)
      else:
        self.add_link(f, m, strictfm)

    # if strictness indicates that middle = last, and middle wasn't just
    # set to first above, make them equal; otherwise add the link between middle/last
    if strictml == 0:
      if m != l:
        self.add_equal(m, l)
      else:
        self.add_link(m, l, strictml)

    # update absolute times
    m.update_absolute_min(f.absolute_min)
    m.update_absolute_max(l.absolute_max)
    f.update_absolute_max(m.absolute_max)
    l.update_absolute_min(m.absolute_min)


  def check_equal(self, name1, name2):
    """Ensure that the call to ``add_equal`` will have the correct arguments."""
    assert isinstance(name1, str) and isinstance(name2, str)
    tp1 = self.time_point(name1)
    tp2 = self.time_point(name2)
    if tp1 is None or not isinstance(tp1, TimePoint):
      # if tp1 is new and tp2 is new, add tp2 as a new point
      if tp2 is None or not isinstance(tp2, TimePoint):
        tp2 = self.add_single(name2)
      self.add_equal(name1, tp2)
    # if tp1 exists and tp2 is new, reverse the order of the arguments
    elif tp2 is None or not isinstance(tp2, TimePoint):
      self.add_equal(name2, tp1)
    # oherwise, both exist
    else:
      if tp1.on_same_chain(tp2) and tp1.pseudo > tp2.pseudo:
        self.add_equal(tp2, tp1)
      else:
        self.add_equal(tp1, tp2)


  def check_before(self, fname, lname, strictfl):
    """Ensure that the arguments are correct for ``add_before``."""
    assert isinstance(fname, str) and isinstance(lname, str) and isinstance(strictfl, int)
    f = self.time_point(fname)
    l = self.time_point(lname)

    # first check to see if this is potentially inconsistent; if so, set strictness so they are equal instead
    if f is not None and l is not None and strictfl < 0 and self.check_inconsistent(f, l, PRED_BEFORE):
      strictfl = 0

    # if the strictness indicates meets (equal), make the points equal
    if strictfl == 0:
      self.check_equal(fname, lname)

    # if last doesn't exist use add_after, since it allows the end point to be new
    elif l is None:
      # if first doesn't exist either, add it
      if f is None:
        self.add_single(fname)
      self.add_after(lname, fname, strictfl)
    
    # otherwise ready for add_before
    else:
      self.add_before(fname, lname, strictfl)


  def check_after(self, lname, fname, strictfl):
    """Ensure that the arguments are correct for ``add_after``."""
    assert isinstance(lname, str) and isinstance(fname, str) and isinstance(strictfl, int)
    l = self.time_point(lname)
    f = self.time_point(fname)

    # first check to see if this is potentially inconsistent; if so, set strictness so they are equal instead
    if l is not None and f is not None and strictfl < 0 and self.check_inconsistent(l, f, PRED_AFTER):
      strictfl = 0

    # if the strictness indicates meets (equal), make the points equal
    if strictfl == 0:
      self.check_equal(lname, fname)

    # if first doesn't exist use add_before, since it allows the start point to be new
    elif f is None:
      # if last doesn't exist either, add it
      if l is None:
        self.add_single(lname)
      self.add_before(fname, lname, strictfl)
    
    # otherwise ready for add_after
    else:
      self.add_after(lname, fname, strictfl)


  def handle_between(self, mname, fname, lname, strictfm, strictml):
    """Attempt to minimize the number of chains by using the appropriate combination of before, after, and between."""
    assert (isinstance(mname, str) and isinstance(fname, str) and isinstance(lname, str) and
            isinstance(strictfm, int) and isinstance(strictml, int))
    m = self.time_point(mname)
    f = self.time_point(fname)
    l = self.time_point(lname)

    # if strictness indicates first and middle equal, make them equal and try to add middle before last
    if l is not None and f is not None and combine_strict(strictfm, strictml) < 0 and self.check_inconsistent(l, f, PRED_AFTER):
      strictfm = 0
      strictml = 0

    # first = middle --> make them equal and try to add middle before last
    if strictfm == 0:
      self.check_equal(mname, fname)
      self.check_before(mname, lname, strictml)
    
    # last = middle --> make them equal and try to add middle after first
    elif strictml == 0:
      self.check_equal(mname, lname)
      self.check_after(mname, fname, strictfm)

    # otherwise use add-between
    else:
      self.add_between(mname, fname, lname, strictfm, strictml)


  def check_between(self, mname, fname, lname, strictfm, strictml):
    """Prepare to call ``add_between`` which requires that first and last points exist."""
    assert (isinstance(mname, str) and isinstance(fname, str) and isinstance(lname, str) and
            isinstance(strictfm, int) and isinstance(strictml, int))
    m = self.time_point(mname)
    f = self.time_point(fname)
    l = self.time_point(lname)

    # first check to see if this is potentially inconsistent; if so, set strictness to make them equal
    if m is not None and f is not None and strictfm < 0 and self.check_inconsistent(m, f, PRED_AFTER):
      strictfm = 0
    if m is not None and l is not None and strictml < 0 and self.check_inconsistent(m, l, PRED_BEFORE):
      strictml = 0
    
    # if middle doesn't exist, make sure first/last exist (adding them if not), and add middle between
    if m is None or not isinstance(m, TimePoint):
      self.check_before(fname, lname, combine_strict(strictfm, strictml))
      self.handle_between(mname, fname, lname, strictfm, strictml)

    # if middle already exists, and is at either extreme of its chain, use before and after to ensure
    # that if first/last don't exist, the minimum number of chains are created
    elif m.first_in_chain() or m.last_in_chain():
      self.check_before(fname, mname, strictfm)
      self.check_after(lname, mname, strictml)

    # otherwise, if either first/last are missing, add last before first using check_after, then middle between
    else:
      self.check_after(lname, fname, combine_strict(strictfm, strictml))
      self.handle_between(mname, fname, lname, strictfm, strictml)


  def enter_point(self, tpname1, stem, tpname2, tpname3=None, strict1=-1, strict2=-1):
    """Enter a particular relation between time points (no events at this stage)."""
    assert (isinstance(tpname1, str) and isinstance(stem, str) and isinstance(tpname2, str) and
            (isinstance(tpname3, str) or tpname3 is None) and
            isinstance(strict1, int) and isinstance(strict2, int))
    if stem == PRED_BETWEEN or tpname1 != tpname2:
      if not stem:
        self.add_single(tpname1)
      elif stem in PREDS_EQUIV:
        self.check_equal(tpname1, tpname2)
      elif stem == PRED_BEFORE:
        self.check_before(tpname1, tpname2, strict1)
      elif stem == PRED_AFTER:
        self.check_after(tpname1, tpname2, strict1)
      elif stem == PRED_BETWEEN:
        if tpname3 is None:
          raise Exception(f'A third point must be given as "tpname3" for predicate "before".')
        self.check_between(tpname1, tpname2, tpname3, strict1, strict2)
      else:
        raise Exception(f'Unsupported predicate stem {stem}')
      

  def register_event(self, eventname):
    """Set up an event point with its start and end timepoints, if one does not already exist."""
    assert isinstance(eventname, str)
    e = self.event_point(eventname)
    if e is None:
      e = EventPoint(eventname)
      self.events[eventname] = e
    return e
      

  def add_event(self, e):
    """Enter a link between the start and end points of an event if one doesn't already exist."""
    assert isinstance(e, EventPoint)
    self.enter_point(e.start, PRED_BEFORE, e.end)


  def enter_duration_min(self, a1, a2, dur):
    """Prepare the arguments for the low-level routine ``add_duration_min``."""
    assert (type(a1) in [str, TimePoint, EventPoint] and type(a2) in [str, TimePoint, EventPoint] and
            type(dur) in [int, float])
    tpname1 = get_end_name(a1)
    tpname2 = get_start_name(a2)
    self.add_duration_min(tpname1, tpname2, dur)


  def enter_duration_max(self, a1, a2, dur):
    """Prepare the arguments for the low-level routine ``add_duration_max``."""
    assert (type(a1) in [str, TimePoint, EventPoint] and type(a2) in [str, TimePoint, EventPoint] and
            type(dur) in [int, float])
    tpname1 = get_end_name(a1)
    tpname2 = get_start_name(a2)
    self.add_duration_max(tpname1, tpname2, dur)


  def enter_reln(self, a1, stem, a2, a3=None, strict1=-1, strict2=-1):
    """Enter the given relation (`stem` `strict1` `strict2`) between the points or events `a1`, `a2`, and possibly `a3`.
    
    It attempts to minimize the number of chains created by ordering the relations in a specific way,
    and using "between" rather than "after"/"before" where possible.

    Notes
    -----
    At this stage there are no absolute time arguments.
    """
    assert (type(a1) in [str, TimePoint, EventPoint] and
            isinstance(stem, str) and
            type(a2) in [str, TimePoint, EventPoint] and
            (type(a3) in [str, TimePoint, EventPoint] or a3 is None) and
            isinstance(strict1, int) and isinstance(strict2, int))
    a1start = get_start_name(a1)
    a2start = get_start_name(a2)
    a3start = get_start_name(a3)
    a1end = get_end_name(a1)
    a2end = get_end_name(a2)
    a3end = get_end_name(a3)

    if a3 is not None:
      self.enter_reln(a2, PRED_DURING, a3)

    # handle individual relations
    if stem in PREDS_EQUIV:
      self.enter_point(a2start, PRED_EQUAL, a2start)
      self.enter_point(a1end, PRED_EQUAL, a2end)
    elif stem == PRED_BEFORE:
      if a3 is None:
        self.enter_point(a1end, PRED_BEFORE, a2start, strict1=strict1)
        self.enter_point(a1start, PRED_BEFORE, a1end)
      else:
        self.enter_point(a1end, PRED_BETWEEN, a3start, a2start, strict2=strict1)
        self.enter_point(a1start, PRED_BETWEEN, a3start, a1end)
    elif stem == PRED_AFTER:
      if a3 is None:
        self.enter_point(a1start, PRED_AFTER, a2end, strict1=strict1)
        self.enter_point(a1end, PRED_AFTER, a1start)
      else:
        self.enter_point(a1start, PRED_BETWEEN, a2end, a3end, strict1=strict1)
        self.enter_point(a1end, PRED_BETWEEN, a1end, a3end)
    elif stem == PRED_DURING:
      if a3 is not None:
        self.enter_point(a2start, PRED_AFTER, a3start)
        self.enter_point(a2end, PRED_BEFORE, a3end)
      self.enter_point(a1start, PRED_BETWEEN, a2start, a2end, strict1=strict1)
      self.enter_point(a1end, PRED_BETWEEN, a1start, a2end, strict2=strict2)
    elif stem == PRED_CONTAINS:
      if a3 is None:
        self.enter_point(a1start, PRED_BEFORE, a2start, strict1=strict1)
        self.enter_point(a1end, PRED_AFTER, a2end, strict1=strict2)
      else:
        self.enter_point(a1start, PRED_BETWEEN, a3start, a2start, strict2=strict1)
        self.enter_point(a1end, PRED_BETWEEN, a2end, a3end, strict1=strict2)
      self.enter_point(a1start, PRED_BEFORE, a1end)
    elif stem == PRED_OVERLAPS:
      if a3 is None:
        self.enter_point(a1end, PRED_BETWEEN, a2start, a2end, strict2=strict2)
        self.enter_point(a1start, PRED_BEFORE, a2start, strict1=strict1)
      else:
        self.enter_point(a1start, PRED_BETWEEN, a3start, a2start, strict2=strict1)
        self.enter_point(a1end, PRED_BETWEEN, a2start, a2end, strict2=strict2)
        self.enter_point(a2end, PRED_BEFORE, a3end)
    elif stem == PRED_OVERLAPPED_BY:
      if a3 is None:
        self.enter_point(a1start, PRED_BETWEEN, a2start, a2end, strict1=strict1)
        self.enter_point(a1end, PRED_AFTER, a2end, strict1=strict2)
      else:
        self.enter_point(a1start, PRED_BETWEEN, a2start, a2end, strict1=strict1)
        self.enter_point(a1end, PRED_BETWEEN, a2end, a3end, strict1=strict2)
        self.enter_point(a3start, PRED_BEFORE, a2start)
    
    if isinstance(a2, EventPoint):
      self.add_event(a2)


  def enter_absolute(self, a1, stem, a2, a3=None, strict1=-1, strict2=-1):
    """Enter a relation when `a2` is an absolute time.
    
    The relation dictates whether it is to be used as an upper or lower bound on the
    absolute time of `a1`, or both. If `a1` is also an absolute time, nothing is done.

    Notes
    -----
    This routine assumes that the other argument is an event (if not, no inconsistencies
    will result - start or end of a point is the point itself - but redundant work may be done).

    The `a3` argument is ignored, although it probably shouldn't be (TODO).
    """
    assert (type(a1) in [str, TimePoint, EventPoint] and
            isinstance(stem, str) and
            isinstance(a2, AbsTime) and
            (type(a3) in [str, TimePoint, EventPoint] or a3 is None) and
            isinstance(strict1, int) and isinstance(strict2, int))
    
    # a2 is absolute time; if a1 is also, don't do anything
    if isinstance(a1, AbsTime):
      return
    
    start = get_start_name(a1)
    end = get_end_name(a1)

    # handle individual relations
    if stem == PRED_BEFORE:
      self.add_absolute_max(end, a2)
    elif stem == PRED_AFTER:
      self.add_absolute_min(start, a2)
    elif stem in PREDS_EQUIV:
      self.add_absolute_min(start, a2)
      self.add_absolute_max(end, a2)
    elif stem == PRED_DURING:
      pass # cannot do anything if during abs time
    elif stem == PRED_CONTAINS:
      self.add_absolute_max(start, a2)
      self.add_absolute_min(end, a2)
    elif stem == PRED_OVERLAPS:
      self.add_absolute_min(start, a2)
    elif stem == PRED_OVERLAPPED_BY:
      self.add_absolute_max(start, a2)

    if isinstance(a1, EventPoint):
      self.add_event(a1)


  def enter_abs_between(self, a1, stem, a2, a3=None, strict1=-1, strict2=-1):
    """Enter a between relation when at least one of the arguments is an absolute time.
    
    If all are absolute times, nothing is done. Otherwise the appropriate absolute time
    bounds are set, or relation entered.
    """
    if not isinstance(a1, AbsTime):
      if isinstance(a2, AbsTime):
        self.add_absolute_min(get_start_name(a1), a2)
      else:
        self.enter_reln(a1, PRED_AFTER, a2, strict1=strict1)
      if isinstance(a3, AbsTime):
        self.add_absolute_max(get_end_name(a1), a3)

    else:
      if not isinstance(a2, AbsTime):
        self.add_absolute_max(get_end_name(a2), a1)
      if not isinstance(a3, AbsTime):
        self.add_absolute_min(get_start_name(a3), a1)

    # ensure that any event always has its start before its end
    if isinstance(a1, EventPoint):
      self.add_event(a1)
    if isinstance(a2, EventPoint):
      self.add_event(a2)    
    if isinstance(a3, EventPoint):
      self.add_event(a3)


  def enter_between(self, a1, stem, a2, a3=None, strict1=-1, strict2=-1):
    """Enter the between relation when none of the arguments are absolute times."""
    assert (type(a1) in [str, TimePoint, EventPoint] and
            isinstance(stem, str) and
            type(a2) in [str, TimePoint, EventPoint] and
            (type(a3) in [str, TimePoint, EventPoint] or a3 is None) and
            isinstance(strict1, int) and isinstance(strict2, int))
    a1start = get_start_name(a1)
    a1end = get_end_name(a1)
    a2end = get_end_name(a2)
    a3start = get_start_name(a3)

    self.enter_point(a1end, PRED_BETWEEN, a2end, a3start, strict2=strict2)

    # ensure that any event always has its start before its end
    if isinstance(a1, EventPoint):
      self.add_event(a1)
    if isinstance(a2, EventPoint):
      self.add_event(a2)    
    if isinstance(a3, EventPoint):
      self.add_event(a3)


  def enter_duration_reln(self, a1, reln, a2, dur):
    """Enter the relation suggested by `reln` and also the duration bound (min or max)."""
    if reln == PRED_AT_LEAST_BEFORE:
      self.enter_reln(a1, PRED_BEFORE, a2, strict1=1)
      self.enter_duration_min(a1, a2, dur)
    elif reln == PRED_AT_MOST_BEFORE:
      self.enter_reln(a1, PRED_BEFORE, a2, strict1=1)
      self.enter_duration_max(a1, a2, dur)
    elif reln == PRED_EXACTLY_BEFORE:
      self.enter_reln(a1, PRED_BEFORE, a2, strict1=1)
      self.enter_duration_min(a1, a2, dur)
      self.enter_duration_max(a1, a2, dur)
    elif reln == PRED_AT_LEAST_AFTER:
      self.enter_reln(a1, PRED_AFTER, a2, strict1=1)
      self.enter_duration_min(a2, a1, dur)
    elif reln == PRED_AT_MOST_AFTER:
      self.enter_reln(a1, PRED_AFTER, a2, strict1=1)
      self.enter_duration_max(a2, a1, dur)
    elif reln == PRED_EXACTLY_AFTER:
      self.enter_reln(a1, PRED_AFTER, a2, strict1=1)
      self.enter_duration_min(a2, a1, dur)
      self.enter_duration_max(a2, a1, dur)


  def enter(self, a1, reln, a2, a3=None):
    """Enter a particular temporal relationship for two (or three) arguments into the graph.

    Each argument may be either a string, a TimePoint, an EventPoint, or an AbsTime. By default, a string will
    be interpreted as the name of a TimePoint that is to be created, or already exists in the graph.
    However, if the name corresponds to an already registered EventPoint (see ``register_event``), then
    that EventPoint will be used.
    
    Parameters
    ----------
    a1 : str, TimePoint, EventPoint, or AbsTime
      The subject of the relation.
    reln : str
      A relation of form "{stem}-{strict1}-{strict2}", where the strictness values are optional
      and may be omitted (see ``pred.py`` for more information).
    a2 : str, TimePoint, EventPoint, or AbsTime
      The object of the relation.
    a3 : str, TimePoint, EventPoint, AbsTime, or None
      The optional second object of the relation (for e.g. "between").
    
    Returns
    -------
    bool
      Whether a relation was successfully entered.
    """
    assert (type(a1) in [str, TimePoint, EventPoint, AbsTime] and
            isinstance(reln, str) and
            type(a2) in [str, TimePoint, EventPoint, AbsTime] and
            (type(a3) in [str, TimePoint, EventPoint, AbsTime] or a3 is None))
    stem, s1, s2 = split_time_pred(reln) 
    enter_res = False

    if self.is_event(a1):
      a1 = self.event_point(a1)
    if self.is_event(a2):
      a2 = self.event_point(a2)
    if a3 is not None and self.is_event(a3):
      a3 = self.event_point(a3)
      
    if stem in PREDS_SEQ + PREDS_CONTAINMENT:
      if a3 is None or isinstance(a3, EventPoint):
        if isinstance(a3, EventPoint):
          self.add_event(a3)
        if isinstance(a2, AbsTime):
          self.enter_absolute(a1, stem, a2, a3, s1, s2)
        elif isinstance(a1, AbsTime):
          self.enter_absolute(a2, inverse_reln(stem), a1, a3, s1, s2)
        else:
          self.enter_reln(a1, stem, a2, a3, s1, s2)
        enter_res = True
    elif stem in [PRED_EQUAL, PRED_SAME_TIME]:
      if isinstance(a1, AbsTime):
        self.enter_absolute(a2, stem, a1)
      elif isinstance(a2, AbsTime):
        self.enter_absolute(a1, stem, a2)
      else:
        self.enter_reln(a1, stem, a2)
      enter_res = True
    elif stem == PRED_BETWEEN:
      if isinstance(a1, AbsTime) or isinstance(a2, AbsTime) or isinstance(a3, AbsTime):
        self.enter_abs_between(a1, stem, a2, a3, s1, s2)
      else:
        self.enter_between(a1, stem, a2, a3, s1, s2)
      enter_res = True
    elif stem in [PRED_AT, PRED_EXACTLY]:
      if not isinstance(a1, AbsTime) and not isinstance(a2, AbsTime) and type(a3) in [int, float]:
        self.enter_duration_reln(a1, reln, a2, a3)
        enter_res = True
    elif stem == PRED_HAS_DURATION:
      if not isinstance(a1, AbsTime) and isinstance(a1, EventPoint) and type(a2) in [int, float]:
        self.enter_duration_reln(self.get_start(a1), PRED_EXACTLY_BEFORE, self.get_end(a1), a2)
        enter_res = True
    else:
      raise Exception(f'Temporal relation "{reln}" not supported.')
    
    return enter_res
  

  def relation(self, a1, a2, effort=DEFAULT_EFFORT):
    """Determine the strongest temporal relation which holds between `a1` and `a2`.

    Parameters
    ----------
    a1 : str, TimePoint, EventPoint, or AbsTime
      The subject of the relation to find.
    a2 : str, TimePoint, EventPoint, or AbsTime
      The object of the relation to find.
    effort : int, default=1
      How much effort to put into the search (0 or 1).
    
    Returns
    -------
    str
      The found relation.
    """
    assert (type(a1) in [str, TimePoint, EventPoint, AbsTime] and
            type(a2) in [str, TimePoint, EventPoint, AbsTime])
    if isinstance(a1, str):
      a1 = self.event_point(a1) if self.is_event(a1) else self.time_point(a1)
    if isinstance(a2, str):
      a2 = self.event_point(a2) if self.is_event(a2) else self.time_point(a2)

    if isinstance(a1, AbsTime) or isinstance(a2, AbsTime):
      return self.find_absolute_reln(a1, a2, effort=effort)
    else:
      return self.find_relation(a1, a2, effort=effort)
    

  def evaluate(self, a1, reln, a2, a3=None, effort=DEFAULT_EFFORT, negated=False):
    """Evaluate whether the given temporal relation is true, false, or unknown.
    
    Parameters
    ----------
    a1 : str, TimePoint, EventPoint, or AbsTime
      The subject of the relation.
    reln : str
      A relation of form "{stem}-{strict1}-{strict2}", where the strictness values are optional
      and may be omitted (see ``pred.py`` for more information).
    a2 : str, TimePoint, EventPoint, or AbsTime
      The object of the relation.
    a3 : str, TimePoint, EventPoint, AbsTime, or None
      The optional second object of the relation (for e.g. "between").
    effort : int, default=1
      How much effort to put into the search (0 or 1).
    negated : bool, default=False
      Whether to negate the result of the evaluation.

    Returns
    -------
    bool or None
      The result of the evaluation, where None is interpreted as "unknown".
    """
    assert (type(a1) in [str, TimePoint, EventPoint, AbsTime] and isinstance(reln, str) and
            type(a2) in [str, TimePoint, EventPoint, AbsTime] and
            (type(a3) in [str, TimePoint, EventPoint, AbsTime] or a3 is None))
    if isinstance(a1, str):
      a1 = self.event_point(a1) if self.is_event(a1) else self.time_point(a1)
    if isinstance(a2, str):
      a2 = self.event_point(a2) if self.is_event(a2) else self.time_point(a2)
    if isinstance(a3, str):
      a3 = self.event_point(a3) if self.is_event(a3) else self.time_point(a3)

    return self.evaluate_time(a1, reln, a2, a3, effort=effort, negated=negated)
    

  def start_of(self, e):
    """Gets the start of `e`, assumed to be an event name."""
    assert isinstance(e, str)
    if self.is_event(e):
      return get_start_name(self.event_point(e))
    else:
      return e
    

  def end_of(self, e):
    """Gets the end of `e`, assumed to be an event name."""
    assert isinstance(e, str)
    if self.is_event(e):
      return get_end_name(self.event_point(e))
    else:
      return e
    

  def elapsed(self, a1, a2, effort=DEFAULT_EFFORT):
    """Calculate the elapsed duration (min/max bounds) between two events or time points."""
    assert (type(a1) in [str, TimePoint, EventPoint] and
            type(a2) in [str, TimePoint, EventPoint])
    if isinstance(a1, str):
      a1 = self.event_point(a1) if self.is_event(a1) else self.time_point(a1)
    if isinstance(a2, str):
      a2 = self.event_point(a2) if self.is_event(a2) else self.time_point(a2)
    return self.calc_duration(self.get_end(a1), self.get_start(a2), effort=effort)
  

  def duration_of(self, a, effort=DEFAULT_EFFORT):
    """Calculate the duration of an event."""
    assert type(a) in [str, TimePoint, EventPoint]
    if isinstance(a, str):
      a = self.event_point(a) if self.is_event(a) else self.time_point(a)
    if isinstance(a, EventPoint):
      return self.calc_duration(self.get_start(a), self.get_end(a), effort=effort)
    else:
      return None


  def format_timegraph(self, verbose=False, lvl=0):
    return '\n\n'.join([v.format(verbose=verbose, lvl=lvl+1) for v in self.timegraph.values()])
  


# ``````````````````````````````````````
# Find subroutines
# ``````````````````````````````````````



def combine_path(s1, s2):
  """Return the strictness value of combining two paths of strictness `s1` and `s2`."""
  strict_before = f'{PRED_BEFORE}-{1}'
  if s1 == strict_before or s2 == strict_before or s1 == True or s2 == True or strict_p(s2):
    return strict_before
  else:
    return PRED_BEFORE
  

def calc_path(sofar, path, link):
  """Return the strictness value resulting from adding `path` and `link` to `sofar`."""
  assert isinstance(link, TimeLink)
  st = link.strict
  return combine_path(sofar, combine_path(path, st))


def check_chain(sofar, tp, item):
  """Check to see if the `item` link is usable, i.e., its to point is before `tp` on the same chain.
  
  If so, return the resulting strictness going to `tp` after `sofar`.
  """
  assert isinstance(tp, TimePoint) and isinstance(item, TimeLink)
  path = item.to_tp.find_pseudo(tp)
  if test_point_answer(PRED_BEFORE, path):
    return combine_path(sofar, path)
  else:
    return None



# ``````````````````````````````````````
# Other
# ``````````````````````````````````````



def strict_p(x):
  """Check if strictness value is strict."""
  return x == 1 or x == '1' or x == True
  

def get_start_name(x):
  if isinstance(x, str):
    return x
  elif isinstance(x, TimePoint):
    return x.name
  elif isinstance(x, EventPoint):
    return x.start
  else:
    return None
  

def get_end_name(x):
  if isinstance(x, str):
    return x
  elif isinstance(x, TimePoint):
    return x.name
  elif isinstance(x, EventPoint):
    return x.end
  else:
    return None