"""Timegraph implementation"""

import math
from collections import UserList

from timegraph.constants import *
from timegraph.abstime import AbsTime, duration_min

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


  def __str__(self):
    return self.name
  

  def __hash__(self):
    return hash(self.name)
  

  def __eq__(self, other):
    return self.chain == other.chain and self.pseudo == other.pseudo
  

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
  """

  def __init__(self):
    self.chain_count = 0
    self.timegraph = {}
    self.metagraph = {}
    self.events = {}


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



# ``````````````````````````````````````
# Other
# ``````````````````````````````````````



def strict_p(x):
  """Check if strictness value is strict."""
  return x == 1 or x == '1' or x == True