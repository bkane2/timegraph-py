"""Time point implementation"""

from collections import UserList

from timegraph.constants import *
from timegraph.util import indent
from timegraph.abstime import AbsTime, duration_min, get_best_duration
from timegraph.pred import test_point_answer

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