"""Absolute time implementation."""

import copy
from datetime import date,datetime,timezone

from timegraph.constants import *
from timegraph.pred import test_point_answer

class AbsTime:
  """A specific absolute time.

  Parameters
  ----------
  time : list[int or str]
    A list structure representing the absolute time data, interpreted
    as year, month, day, hour, minute, second. Each value may either be a
    number or a symbol representing a variable argument.
  """

  def __init__(self, time=None):
    self.update(time)


  def update(self, time=None):
    """Update this absolute time to the given time (or current if none is given)."""
    if isinstance(time, datetime):
      self.time = self._parse_datetime(time)
    elif type(time) in [int, float]:
      self.time = self._parse_timestamp(time)
    elif isinstance(time, list) and all([type(x) in [int, str] for x in time]) and len(time) <= 6:
      time = [int(t) if (isinstance(t, str) and t.isdigit()) else t for t in time]
      self.time = time
    elif time is None:
      self.time = self._parse_datetime(datetime.now())
    else:
      raise Exception("Invalid format given for 'time'.")
    return self
    

  def to_datetime(self):
    """Convert this absolute time to a datetime object (assuming no variable arguments)."""
    return self.to_datetime_bounds()[0]
    

  def to_datetime_bounds(self):
    """Convert this absolute time to lower/upper bound datetime objects."""
    args_l = { k:v for k,v in zip(DATETIME_ARGS, self.time) }
    args_u = { k:v for k,v in zip(DATETIME_ARGS, self.time) }
    for k, v in args_l.items():
      if not isinstance(v, int):
        args_l[k] = DATETIME_LOWER[k]
    for k in DATETIME_REQUIRED_ARGS:
      if k not in args_l:
        args_l[k] = DATETIME_LOWER[k]
    for k, v in args_u.items():
      if not isinstance(v, int):
        args_u[k] = DATETIME_UPPER[k]
    for k in DATETIME_REQUIRED_ARGS:
      if k not in args_u:
        args_u[k] = DATETIME_UPPER[k]
    return datetime(**args_l), datetime(**args_u)
  

  def to_num(self):
    """Convert to a numerical POSIX representation (assuming no variable arguments)."""
    return self.to_datetime().timestamp()
  

  def to_record(self):
    """Convert to a slot/value record structure."""
    return ['$', 'date+time']+' '.join([f':{k} {v}' for k,v in zip(DATETIME_ARGS, self.time)]).split()
  

  def has_symbols(self):
    """Check if this time has symbol/variable arguments."""
    return not all([isinstance(x, int) for x in self.time])
  

  def calc_add_dur(self, dur):
    """Add `dur` seconds to the absolute time, returning a new absolute time."""
    if not isinstance(dur, int) or dur == 0 or self.has_symbols():
      return self.copy()
    numdur = self.to_num() + dur
    return AbsTime(numdur)
  

  def update_add_dur(self, dur):
    """Update the absolute time to `dur` seconds after."""
    if not isinstance(dur, int) or dur == 0 or self.has_symbols():
      return self
    numdur = self.to_num() + dur
    return self.update(numdur)
  

  def calc_sub_dur(self, dur):
    """Subtract `dur` seconds to the absolute time, returning a new absolute time."""
    if not isinstance(dur, int) or dur == 0 or self.has_symbols():
      return self.copy()
    numdur = self.to_num() - dur
    if numdur >= 0:
      return AbsTime(numdur)
    else:
      return self.copy()
    
    
  def update_sub_dur(self, dur):
    """Update the absolute time to `dur` seconds before."""
    if not isinstance(dur, int) or dur == 0 or self.has_symbols():
      return self
    numdur = self.to_num() - dur
    if numdur >= 0:
      return self.update(numdur)
    else:
      return self
    

  def merge_abs_min(self, newabs, max):
    """Merge the minimum of this time and a new time, taking the maximum of the two."""
    assert isinstance(newabs, AbsTime) and isinstance(max, AbsTime)
    return AbsTime(merge_min(self.time, newabs.time, max.time))
  

  def merge_abs_max(self, newabs, min):
    """Merge the maximum of this time and a new time, taking the minimum of the two."""
    assert isinstance(newabs, AbsTime) and isinstance(min, AbsTime)
    return AbsTime(merge_max(self.time, newabs.time, min.time))
    

  def re_calc_abs_min(self, oldabs, max, duration):
    """Compute the new absolute time `duration` seconds after `propabs`, taking the maximum of that and `oldabs`."""
    assert isinstance(oldabs, AbsTime) and isinstance(max, AbsTime)
    new = self.calc_add_dur(duration)
    new.time = choose_max(oldabs.time, new.time, max.time)
    return new


  def re_calc_abs_max(self, oldabs, min, duration):
    """Compute the new absolute time `duration` seconds before `propabs`, taking the minimum of that and `oldabs`."""
    assert isinstance(oldabs, AbsTime) and isinstance(min, AbsTime)
    new = self.calc_sub_dur(duration)
    new.time = choose_min(oldabs.time, new.time, min.time)
    return new


  def calc_duration_min(self, other):
    """Calculates the minimum duration between this and another absolute time."""
    if not other or not isinstance(other, AbsTime):
      return None
    diff = other.to_num() - self.to_num()
    return diff if diff >= 0 else 0
  

  def calc_duration_max(self, other):
    """Calculates the maximum duration between this and another absolute time.
    
    Notes
    -----
    This works OK for all numeric absolute times, but not for ones with symbols.
    """
    if not other or not isinstance(other, AbsTime):
      return None
    if self.has_symbols() or other.has_symbols():
      return None
    return other.to_num() - self.to_num()
  

  def compare(self, other):
    """Compare this to another absolute time and return the relation between them."""
    assert isinstance(other, AbsTime)
    return compare(self.time, other.time)


  def copy(self):
    return copy.copy(self)
  

  def __str__(self):
    return ', '.join([f'{k}: {v}' for k,v in zip(DATETIME_ARGS, self.time)])
  

  def __eq__(self, other):
    if not isinstance(other, AbsTime):
      return False
    return self.time == other.time
    
  
  def _parse_datetime(self, dt):
    args = dt.strftime("%Y-%m-%d-%H-%M-%S").split('-')
    return [int(x) for x in args]
  

  def _parse_timestamp(self, ts):
    dt = datetime.fromtimestamp(ts)
    return self._parse_datetime(dt)
  


# ``````````````````````````````````````
# Utilities
# ``````````````````````````````````````



def get_extremum(abs1, abs2, max=True):
  """Return the maximum/minimum of `abs1` and `abs2` (or return None if cannot be compared)."""
  if not abs1 or not abs2:
    return []
  e1 = abs1[0]
  e2 = abs2[0]
  if isinstance(e1, int):
    if isinstance(e2, int):
      if (max and e1 > e2) or (not max and e1 < e2):
        return abs1
      elif (max and e1 < e2) or (not max and e1 > e2):
        return abs2
      else:
        return [e1] + get_extremum(abs1[1:], abs2[1:], max=max)
    else:
      return abs1
  else:
    if isinstance(e2, int):
      return abs2
    elif e1 == e2:
      return [e1] + get_extremum(abs1[1:], abs2[1:], max=max)
    else:
      return abs1
    

def replace_unknowns(abs1, abs2):
  """Replace variable terms in `abs1` with numbers from `abs2` if possible."""
  return [a if isinstance(a, int) else b if isinstance(b, int) else a for a, b in zip(abs1, abs2)]


def choose_max(oldabs, newabs, max):
  """Return the maximum of `oldabs` and `newabs`, as long as it is no greater than `max`."""
  if not oldabs:
    return newabs
  if not newabs:
    return oldabs
  
  setabs = get_extremum(oldabs, newabs, max=True)
  if not test_point_answer(PRED_AFTER, compare(setabs, max)):
    return setabs
  else:
    return oldabs
  

def choose_min(oldabs, newabs, min):
  """Return the minimum of `oldabs` and `newabs`, as long as it is no less than `min`."""
  if not oldabs:
    return newabs
  if not newabs:
    return oldabs
  
  setabs = get_extremum(oldabs, newabs, max=False)
  if not test_point_answer(PRED_BEFORE, compare(setabs, min)):
    return setabs
  else:
    return oldabs
  

def merge_min(oldabs, newabs, max):
  """Merge the minimum of an old absolute time and a new time, taking the maximum of the two.
  
  The maximum absolute time is taken if one is strictly greater than the other,
  and constant or variable names are replaced by numbers if possible.
  """
  if not oldabs:
    return newabs
  if not newabs:
    return oldabs
  
  newmin = choose_max(replace_unknowns(oldabs, newabs), newabs, max)
  return newmin if newmin == newabs else oldabs


def merge_max(oldabs, newabs, min):
  """Merge the maximum of an old absolute time and a new time, taking the minimum of the two.
  
  The minimum absolute time is taken if one is strictly greater than the other,
  and constant or variable names are replaced by numbers if possible.
  """
  if not oldabs:
    return newabs
  if not newabs:
    return oldabs
  
  newmax = choose_min(replace_unknowns(oldabs, newabs), newabs, min)
  return newmax if newmax == newabs else oldabs


def compare_elements(abs1, abs2):
  """Compare two absolute times element-by-element."""
  if not abs1:
    return PRED_SAME_TIME
  a1 = abs1[0]
  a2 = abs2[0]
  if a1 == a2:
    return compare_elements(abs1[1:], abs2[1:])
  elif isinstance(a1, int) and isinstance(a2, int):
    strict = 1
    return f'{PRED_AFTER}-{strict}' if a1 > a2 else f'{PRED_BEFORE}-{strict}'
  return PRED_UNKNOWN


def compare(abs1, abs2):
  """Return the relation between the two absolute times `abs1` and `abs2`."""
  if not abs1 or not abs2:
    return PRED_UNKNOWN
  else:
    return compare_elements(abs1, abs2)


def duration_min(d1, d2):
  """Determine the appropriate duration to use, i.e., the given one or the one calculated from the absolute times."""
  if not d1 or d1 == float('-inf'):
    if not d2 or d2 == float('-inf'):
      return 0
    else:
      return d2
  elif not d2 or d2 == float('-inf'):
    return d1
  else:
    return min(d1, d2)
  

def combine_durations(d1, d2):
  """Add the two durations together, where each duration is a tuple ``(min, max)``.
  
  If the min of either is None, it is considered 0;
  likewise if the max is, it is considered +infinity.
  """
  oldmin, oldmax = d1
  newmin, newmax = d2

  if oldmin is None and newmin is None:
    calcmin = 0
  elif oldmin is None:
    calcmin = newmin
  elif newmin is None:
    calcmin = oldmin
  else:
    calcmin = oldmin + newmin
  
  if oldmax is None or newmax is None:
    calcmax = float('inf')
  else:
    calcmax = oldmax + newmax

  return (calcmin, calcmax)


def get_best_duration(d1, d2):
  """Return the best duration between two durations, where each duration is a tuple ``(min, max)``.
  
  Since both are assumed to be true for the same points, we just pick the best minimum
  (the maximum one) and the best maximum (the minimum one).
  """
  min1 = 0 if d1[0] is None else d1[0]
  min2 = 0 if d2[0] is None else d2[0]
  max1 = float('inf') if d1[1] is None else d1[1]
  max2 = float('inf') if d2[1] is None else d2[1]
  return (max(min1, min2), min(max1, max2))