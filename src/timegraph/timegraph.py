"""Timegraph implementation"""

import math
from collections import UserList

from timegraph.constants import *
from timegraph.util import indent
from timegraph.abstime import AbsTime, duration_min, combine_durations, get_best_duration
from timegraph.pred import test_point_answer, inverse_reln, split_time_pred, build_pred

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
  alternate_names : list[str]
    A list of names of alternative points collapsed into this.

  Parameters
  ----------
  name : str
  """

  def __init__(self, name, chain=None, pseudo=PSEUDO_INIT):
    self.name = name
    self.chain = chain
    self.pseudo = pseudo
    self.min_pseudo = float('-inf')
    self.max_pseudo = float('inf')
    self.absolute_min = None
    self.absolute_max = None
    self.ancestors = TimeLinkList()
    self.xancestors = TimeLinkList()
    self.descendants = TimeLinkList()
    self.xdescendants = TimeLinkList()
    self.alternate_names = []
  

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
    p2 = tp.pseudo
    return p2 > self.min_pseudo and p2 < self.max_pseudo
  

  def find_pseudo(self, tp):
    """Find the most strict relation possible between this point and `tp` using their pseudo times."""
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
    return self.chain == tp.chain


  def first_in_chain(self):
    """Check if this is the first point on its chain."""
    return True if not self.ancestors else False
  

  def last_in_chain(self):
    """Check if this is the last point on its chain."""
    return True if not self.descendants else False
  

  def update_first(self):
    """If this point is earlier on its chain than the current first point, update the first pointer."""
    meta = self.chain
    first = meta.first
    if not first or self.pseudo < first.pseudo:
      meta.first = self
  

  def add_ancestor_link(self, timelink):
    """Add a link on the in chain ancestor list."""
    self.ancestors.add(timelink)


  def add_descendant_link(self, timelink):
    """Add a link on the in chain descendant list."""
    self.descendants.add(timelink)


  def add_xancestor_link(self, timelink):
    """Add a link on the cross chain ancestor list."""
    self.xancestors.add(timelink)


  def add_xdescendant_link(self, timelink):
    """Add a link on the cross chain descendant list."""
    self.xdescendants.add(timelink)


  def prop_absmin(self):
    """Propagate absolute time minimum from the given point to any descendants."""
    dlist = self.descendants
    xdlist = self.xdescendants

    # Propagate only to first in chain descendant - since it is recursive it will
    # get the rest of the chain anyway
    if dlist:
      dlist[0].prop_min_to_point()
    
    # Propagate to all x-descendants
    for xitem in xdlist:
      xitem.prop_min_to_point()


  def prop_absmax(self, oldabs):
    """Propagate absolute time maximum from the given point to any ancestors."""
    alist = self.ancestors
    xalist = self.xancestors

    # Propagate only to first in chain ancestor - since it is recursive it will
    # get the rest of the chain anyway
    if alist:
      alist[0].prop_max_to_point(oldabs)
    
    # Propagate to all x-ancestors
    for xitem in xalist:
      xitem.prop_max_to_point(oldabs)


  def update_absolute_min(self, abs):
    """Add a new absolute minimum time to this point."""
    max = self.absolute_max
    oldabs = self.absolute_min
    newabs = oldabs.merge_abs_min(abs, max)
    if not oldabs == newabs:
      self.absolute_min = newabs
      self.prop_absmin()


  def update_absolute_max(self, abs):
    """Add a new absolute maximum time to this point."""
    min = self.absolute_min
    oldabs = self.absolute_max
    newabs = oldabs.merge_abs_max(abs, min)
    if not oldabs == newabs:
      self.absolute_max = newabs
      self.prop_absmax(oldabs)


  def duration_between(self, tp):
    """Determine the duration between this and another point based on their absolute times."""
    min1 = self.absolute_min
    max1 = self.absolute_max
    min2 = tp.absolute_min
    max2 = tp.absolute_max
    return (max1.calc_duration_min(min2), min1.calc_duration_max(max2))


  def compare_absolute_times(self, tp):
    """Return the relation between this point and `tp` based on their absolute times."""
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
    return self.chain == other.chain and self.pseudo == other.pseudo
  

  def format(self, verbose=False, lvl=0):
    parts = []
    parts.append(f'{indent(lvl)}Node {self.name}')
    parts.append(f'{indent(lvl)}Chain {self.chain.chain_number}')
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
    self.from_tp = from_tp
    self.to_tp = to_tp
    self.strict = strict
    self.duration_min = 0
    self.duration_max = float('inf')


  def from_chain_number(self):
    return self.from_tp.chain.chain_number
  

  def from_pseudo(self):
    return self.from_tp.pseudo
  

  def to_chain_number(self):
    return self.to_tp.chain.chain_number
  

  def to_pseudo(self):
    return self.to_tp.pseudo
  

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
    if (d > 0 and not self.strict) or (not self.duration_min or d > self.duration_min):
      tp1 = self.from_tp
      tp2 = self.to_tp
      if d > 0 and not self.strict:
        self.strict = True
        if tp1.on_same_chain(tp2):
          pass
          # TODO
          # tp1.add_strictness(tp2)
      if not self.duration_min or d > self.duration_min:
        self.duration_min = d
        tp1.update_absolute_max(tp2.absolute_max.calc_sub_dur(d))
        tp2.update_absolute_min(tp1.absolute_min.calc_add_dur(d))


  def update_duration_max(self, d):
    """Add a maximum duration to this link."""
    if not self.duration_max or d < self.duration_max:
      self.duration_max = d


  def __eq__(self, other):
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
      return (lk.from_chain_number() > item.from_chain_number()
            or (lk.from_chain_number() == item.from_chain_number()
                and (lk.from_pseudo() > item.from_pseudo()
                      or (lk.from_pseudo() == item.from_pseudo()
                          and (lk.to_chain_number() > item.to_chain_number()
                              or (lk.to_chain_number() == item.to_chain_number()
                                  and lk.to_pseudo() >= item.to_pseudo()))))))
    
    def ins_here(llist, item):
      lk = llist[0]
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
      if dlist:
        p = dlist[0].to_tp
        p.pseudo = last.pseudo_after()
        renumber_next(p, p.descendants)

    f = self.first
    f.pseudo = PSEUDO_INIT
    renumber_next(f, f.descendants)



# ``````````````````````````````````````
# EventPoint
# ``````````````````````````````````````



class EventPoint:
  """A node representing an event (i.e., an interval with some start and end time points).
  
  Attributes
  ----------
  name : str
    The symbol denoting the event.
  start : TimePoint
    The start time point.
  end : TimePoint
    The end time point.

  Parameters
  ----------
  name : str
  """

  def __init__(self, name):
    self.name = name
    self.start = None
    self.end = None



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
    return self.timegraph[name] if name in self.timegraph else None
  

  def time_chain(self, chain_number):
    """Return the meta node corresponding to `chain_number` if there is one, otherwise None."""
    return self.metagraph[chain_number] if chain_number in self.metagraph else None
  

  def event_point(self, name):
    """Return the event point corresponding to `name`, if there is one, otherwise None."""
    return self.events[name] if name in self.events else None
  

  def add_meta_link(self, timelink):
    """Add a link to the meta graph for the appropriate chain."""
    if not timelink.from_chain_number() == timelink.to_chain_number():
      mn = self.time_chain(timelink.from_chain_number())
      if mn:
        mn.connections.add(timelink)


  def remove_meta_link(self, timelink):
    """Remove a link from the meta graph."""
    if not timelink.from_chain_number() == timelink.to_chain_number():
      mn = self.time_chain(timelink.from_chain_number())
      if mn:
        mn.connections.remove(timelink)


  def add_link(self, tp1, tp2, strict12):
    """Add a link between `tp1` and `tp2` with the appropriate strictness.
    
    If the two points are on different chains, a meta link is also added.
    """
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
    self.remove_meta_link(timelink)
    linklist.remove(timelink)


  def update_links(self, tp1, tp2, type):
    """Update the links of `type` from `tp1` to `tp2`, where `type` is "descendants", "ancestors", "xdescendants", or "xancestors".
    
    If `type` is "(x)descendants", for each link in `tp1`'s (x)descendants list, the "to" point ancestor list
    has this link removed, and then the link is added using `tp2` as the ancestor.

    If `type` is "(x)ascendants", for each link in `tp1`'s (x)ancestors list, the "from" point descendant list
    has this link removed, and then the link is added using `tp2` as the descendant.
    """
    if type not in POINT_LINK_PAIRS.keys():
      raise Exception('Invalid type argument')
    linklist = getattr(tp1, type)
    for link in linklist:
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
    chain2 = tp2.chain
    pseudo2 = tp2.pseudo
    if tp1.on_same_chain(tp2):
      dlist = tp1.descendants
    else:
      dlist = tp1.xdescendants
    link = None
    for item in dlist:
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
    self.update_links(tp1, tp2, 'ancestors')
    self.update_links(tp1, tp2, 'xancestors')
    self.update_links(tp1, tp2, 'descendants')
    self.update_links(tp1, tp2, 'xdescendants')


  def add_single(self, tpname):
    """Add a single point to the net on a new chain."""
    tp = TimePoint(tpname, chain=self.newchain())
    self.timegraph[tpname] = tp
    tp.update_first()
    return tp
  

  def add_absolute_min(self, tpname, abs):
    """Add an absolute minimum time to `tpname` (creating the point if it doesn't exist)."""
    if tpname not in self.timegraph:
      self.add_single(tpname)
    self.timegraph[tpname].update_absolute_min(abs)


  def add_absolute_max(self, tpname, abs):
    """Add an absolute maximum time to `tpname` (creating the point if it doesn't exist)."""
    if tpname not in self.timegraph:
      self.add_single(tpname)
    self.timegraph[tpname].update_absolute_max(abs)

  
  def new_duration_min(self, tp1, tp2, d):
    """Create a duration minimum between `tp1` and `tp2`."""
    link = self.find_link(tp1, tp2)
    link.update_duration_min(d)


  def add_duration_min(self, tpname1, tpname2, d):
    """Add a duration minimum between `tpname1` and `tpname2`."""
    if tpname1 not in self.timegraph or tpname2 not in self.timegraph:
      raise Exception(f'One of {tpname1} or {tpname2} does not exist in the timegraph.')
    tp1 = self.timegraph[tpname1]
    tp2 = self.timegraph[tpname2]
    self.new_duration_min(tp1, tp2, d)


  def new_duration_max(self, tp1, tp2, d):
    """Create a duration maximum between `tp1` and `tp2`."""
    link = self.find_link(tp1, tp2)
    link.update_duration_max(d)


  def add_duration_max(self, tpname1, tpname2, d):
    """Add a duration maximum between `tpname1` and `tpname2`."""
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
    self.rel_table = {}
    res = self.search_meta(tp1, tp2, [tp1.chain.chain_number], None)
    self.rel_table = {}
    return res
  

  def find_reln(self, tp1, tp2, effort=0):
    """Find the most strict relation that holds between `tp1` and `tp2`.
    
    `effort` indicates how hard it should search (0 or 1).
    """
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
  

  def find_point(self, t1, t2, effort=0):
    """Find the most strict relationship that holds between `t1` and `t2`, which may be either absolute times or points.
    
    `effort` indicates how hard it should search (0 or 1).
    """
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
  

  def find_absolute(self, a1, a2, effort=0):
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
  

  def find_absolute_reln(self, a1, a2, effort=0):
    """Return the relationship between `a1` and `a2`, which may be events with absolute times.
    
    `effort` indicates how hard it should search (0 or 1).
    """
    if isinstance(a1, AbsTime) and isinstance(a2, AbsTime):
      return self.find_absolute(a1, a2, effort=effort)
    a1start = get_start(a1)
    a2start = get_start(a2)
    a1end = get_end(a1)
    a2end = get_end(a2)
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
    desclist = tp1.descendants + tp1.xdescendants
    usedur = None
    curdur = None

    for item in desclist:
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
  

  def calc_duration(self, tp1, tp2, effort=0):
    """Determine the duration between two points.
    
    If either point doesn't exist, returns unknown. If they exist, it first
    determines the duration based on their absolute times. If the min is
    greater than the max, the points are reversed. If we have a range, and
    the effort level `effort` (0 or 1) indicates to continue trying,
    ``search_for_duration`` is called to determine the best duration along
    any path. The best between this and the absolute time duration is returned.
    """
    if not tp1 or not tp2:
      return (0, float('inf'))
    durans = tp1.duration_between(tp2)
    durmin, durmax = durans
    if (not durmin or durmax == float('inf') or not durmax) and effort > 0:
      durans = get_best_duration(durans, self.search_for_duration(tp1, tp2, None, [tp1.name]))
    durmin, durmax = durans
    durmin = 0 if not durmin else durmin
    durmax = float('inf') if not durmax else durmax
    return (durmin, durmax)
  

  def find_relation(self, a1, a2, effort=0):
    """Return the most strict relation found between `a1` and `a2`, which may be either events or points.
    
    It determines relationships between the starts, ends, and start of one, end of the other, and uses
    those results to determine the actual relation.

    `effort` indicates how hard it should search (0 or 1).
    """
    if a1 == a2:
      return PRED_SAME_TIME
    if not type(a1) in [EventPoint, TimePoint] or not type(a2) in [EventPoint, TimePoint]:
      return PRED_UNKNOWN
    
    a1start = get_start(a1)
    a1end = get_end(a1)
    a2start = get_start(a2)
    a2end = get_end(a2)
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
  st = link.strict
  return combine_path(sofar, combine_path(path, st))


def check_chain(sofar, tp, item):
  """Check to see if the `item` link is usable, i.e., its to point is before `tp` on the same chain.
  
  If so, return the resulting strictness going to `tp` after `sofar`.
  """
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


def get_start(x):
  """Get the start of a given concept.
  
  `x` is either an event, absolute time, or time point. In the first two
  cases, return the start time point and the absolute time itself, respectively. Otherwise,
  just return the time point.
  """
  if not x:
    return None
  elif isinstance(x, EventPoint):
    return x.start
  elif isinstance(x, AbsTime):
    return x
  elif isinstance(x, TimePoint):
    return x
  else:
    return None


def get_end(x):
  """Get the end of a given concept.
  
  `x` is either an event, absolute time, or time point. In the first two
  cases, return the end time point and the absolute time itself, respectively. Otherwise,
  just return the time point.
  """
  if not x:
    return None
  elif isinstance(x, EventPoint):
    return x.end
  elif isinstance(x, AbsTime):
    return x
  elif isinstance(x, TimePoint):
    return x
  else:
    return None