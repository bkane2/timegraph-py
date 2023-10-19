"""Timegraph implementation"""

from enum import Enum
from timegraph.abstime import TimePoint

class TLNode:
  """TODO"""

  def __init__(self, labels, start=None, end=None):
    if not isinstance(labels, list):
      labels = [labels]
    self.labels = labels
    self.start = start
    self.end = end

  def __str__(self):
    return str(self.labels[0])

  def __hash__(self):
    return hash(self.labels[0])
  

class TRel(Enum):
  L = '<'
  LEQ = '<='
  NEQ = '!='
  

class TLEdge:
  """TODO"""

  def __init__(self, v, w, trel):
    self.v = v
    self.w = w
    self.trel = trel

  def __str__(self):
    return str((self.v, self.w, self.trel.value))
  
  def __hash__(self):
    return hash((self.v, self.w))


class TLGraph:
  """TODO"""

  def __init__(self):
    self.nodes = set()
    self.edges = set()


class TimeGraph(TLGraph):
  """TODO"""

  def __init__(self):
    pass