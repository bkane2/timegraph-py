"""Timegraph implementation"""

from timegraph.constants import *
from timegraph.abstime import AbsTime

# ``````````````````````````````````````
# Definitions
# ``````````````````````````````````````



class TimePoint:
  """A node corresponding to a particular time point in a timegraph.
  
  Attributes
  ----------
  id : str
    The ID of the time point.
  chain : MetaNode
    The meta-node for the chain that this point belongs to.
  pseudo : int
    pseudo time for this point.
  min_point_name : str (TODO)
    Name of the earliest time point this is equal to.
  max_point_name : str (TODO)
    Name of the latest point this is equal to.
  absolute_min : AbsTime, optional
    Absolute time minimum for this point.
  absolute_max : AbsTime, optional
    Absolute time maximum for this point.
  ancestors : list[TimePoint]
    A list of in-chain ascendants.
  xancestors : list[TimePoint]
    A list of cross-chain ascendants.
  descendants : list[TimePoint]
    A list of in-chain descendants.
  xdescendants : list[TimePoint]
    A list of cross-chain descendants.
  alternate_names : list[str]
    A list of names of alternative points collapsed into this.

  Parameters
  ----------
  name : str
  """

  def __init__(self, name):
    self.name = name
    self.chain = None
    self.pseudo = None
    self.min_point_name = None
    self.max_point_name = None
    self.absolute_min = None
    self.absolute_max = None
    self.ancestors = []
    self.xancestors = []
    self.descendants = []
    self.xdescendants = []
    self.alternate_names = []


class TimeLink:
  """A link between two time points.
  
  Attributes
  ----------
  from_name : str
    Name of point link is from.
  to_name : str
    Name of point link is to.
  strict : bool
    Indicates strictness.
  duration_min : float (TODO)
    Minimum duration between `to` and `from` points.
  duration_max : float (TODO)
    Maximum duration between `to` and `from` points.
  """

  def __init__(self):
    self.from_name = None
    self.to_name = None
    self.strict = False
    self.duration_min = 0
    self.duration_max = float('inf')


class MetaNode:
  """A node in the metagraph connecting time chains.
  
  Attributes
  ----------
  chain_number : int
    The chain number of this metanode.
  first : TimePoint (TODO)
    The first time point in the chain for this metanode.
  connections : list[TimeLink]
    All cross-chain links.

  Parameters
  ----------
  chain_number : int
  first : TimePoint, optional
  connections : list[TimeLink], optional
  """

  def __init__(self, chain_number, first=None, connections=[]):
    self.chain_number = chain_number
    self.first = first
    self.connections = connections


class EventNode:
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


class TimeGraph:
  """A timegraph structure.
  
  Attributes
  ----------
  chain_count : int
    An index marking the number of chains in the timegraph.
  timegraph : dict[str, TimePoint]
    A hash table of time points constituting the timegraph.
  metagraph : dict[str, MetaNode] (TODO)
    A hash table of meta nodes.
  events : dict[str, EventNode] (TODO)
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

