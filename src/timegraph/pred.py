"""Functions for processing and evaluating temporal predicates.

Some of the temporal predicates have one or two strictness values
embedded in them (eg. before-1, between-0-1). The possible strictness
values and their meanings are as follows:

  - 0 : zero space between   (meets)
  - 1 : greater-than-zero space between (strict < or >)
  - -1 : 0 or 1  (<= or >= depending on stem)
"""

from timegraph.constants import *

# ``````````````````````````````````````
# Processing
# ``````````````````````````````````````



def split_time_pred(pred):
  """Divide the temporal predicate into a stem and strictness indicator.
  
  Parameters
  ----------
  pred : str
    A predicate of form ``stem[-s1[-s2]]``, e.g., ``before``, ``before-1``,
    ``before-0-1``, ``before--1``, etc.
  
  Returns
  -------
  tuple[str, int, int]
    A tuple of form (stem, strict1, strict2)
  """
  # Preprocess any predicates containing '-'
  for p in PREDS:
    pred = pred.replace(p, p.replace('-', '_'))

  s1 = -1
  s2 = -1
  parts = pred.split('-')
  stem = parts[0]
  parts = parts[1:]
  if parts:
    s1 = parts[0]
    if not s1.isdigit():
      s1 = -1
    parts = parts[1:]
  if parts:
    s2 = parts[0]
    if not s2.isdigit():
      s2 = -1

  return (stem.replace('_', '-'), int(s1), int(s2))


def build_pred(stem, strict1=-1, strict2=-1):
  """Build a predicate symbol from the given stem and optional strictness values."""
  if strict1 < 0:
    if strict2 < 0:
      return stem
    else:
      return f'{stem}--{strict2}'
  elif strict2 < 0:
    return f'{stem}-{strict1}'
  else:
    return f'{stem}-{strict1}-{strict2}'
  

def more_strict(pred):
  """Return the strictest version of the given pred."""
  stem, s1, s2 = split_time_pred(pred)
  if stem in PREDS_EQUIV:
    return pred
  elif stem in PREDS_SEQ:
    return build_pred(stem, 1, -1) if s1 < 0 else pred
  else:
    s1 = 1 if s1 < 0 else s1
    s2 = 1 if s2 < 0 else s2
    return build_pred(stem, s1, s2)
  

def inverse_stem(pred):
  return INVERSE_PREDS[pred] if pred in INVERSE_PREDS else PRED_UNKNOWN


def inverse_reln(reln):
  """Return the inverse relation of `reln`."""
  if not reln:
    return None
  stem, s1, s2 = split_time_pred(reln)
  return build_pred(inverse_stem(stem), s1, s2)
  

def combine_strict(strict1, strict2):
  """Combine the strictness values of two arcs to determine what a combined arc would be.
  
    - '<' + x --> '<'
    - x + '<' --> '<'
    - x + x --> x
    - otherwise --> '<='
  """
  if strict1 == strict2:
    return strict1
  elif strict1 == 1:
    return strict1
  elif strict2 == 1:
    return strict2
  elif strict1 == 0:
    return strict2
  elif strict2 == 0:
    return strict1
  else:
    return -1



# ``````````````````````````````````````
# Comparison
# ``````````````````````````````````````



def compare_strict(s1, s2):
  """Compare the two strictness values for the same stem and decide what relationship would hold."""
  if s1 == s2:
    return REL_EQUIVALENT
  elif s1 < 0:
    return REL_SUBSUMES
  elif s2 < 0:
    return REL_SUBSUMED
  else:
    return REL_DISJOINT


def compare_inverse_strict(s1, s2):
  """Compare the two strictness values for stems which are the inverse of each other."""
  if s1 == 1 or s2 == 1:
    return REL_DISJOINT
  elif s1 == 0 and s2 == 0:
    return REL_EQUIVALENT
  else:
    return REL_INTERSECTS
  

def compare_single(stem1, s1, stem2, s2):
  """Compare two predicates which may each have one strictness value associated with them."""
  if stem1 in PREDS_EQUIV and stem2 in PREDS_EQUIV:
    return REL_EQUIVALENT
  
  elif stem1 == stem2:
    return compare_strict(s1, s2)
  
  # For points, after-0 and before-0 are the same thing; and after and before intersect.
  # Not true for events or combos.
  elif stem1 == inverse_stem(stem2):
    return compare_inverse_strict(s1, s2)
  
  # For points, after-0 and before-0 are equivalent to equal.
  # But for events or combos, they are not (subsumes?)
  elif stem1 in PREDS_EQUIV:
    if s2 == 0:
      return REL_EQUIVALENT
    elif s2 == 1:
      return REL_DISJOINT
    else:
      return REL_SUBSUMED
  elif stem2 in PREDS_EQUIV:
    if s1 == 0:
      return REL_EQUIVALENT
    elif s1 == 1:
      return REL_DISJOINT
    else:
      return REL_SUBSUMES
  
  else:
    return REL_UNKNOWN


def determine_split(stem, s1, s2):
  """Determine what the predicates involved are when splitting a complex relation into several simple relations."""
  if stem in PREDS_EQUIV:
    return [(stem, -1),
            (stem, -1),
            (PRED_BEFORE, -1),
            (PRED_AFTER, -1)]
  elif stem == PRED_DURING:
    return [(PRED_AFTER, s1),
            (PRED_BEFORE, s2),
            (PRED_BEFORE, combine_strict(-1, s2)),
            (PRED_AFTER, combine_strict(s1, -1))]
  elif stem == PRED_CONTAINS:
    return [(PRED_BEFORE, s1),
            (PRED_AFTER, s2),
            (PRED_BEFORE, combine_strict(s1, -1)),
            (PRED_AFTER, combine_strict(-1, s2))]
  elif stem == PRED_OVERLAPS:
    return [(PRED_BEFORE, s1),
            (PRED_BEFORE, s2),
            (PRED_BEFORE, combine_strict(s1, s2)),
            (PRED_AFTER, -1)]
  elif stem == PRED_OVERLAPPED_BY:
    return [(PRED_AFTER, s1),
            (PRED_AFTER, s2),
            (PRED_BEFORE, -1),
            (PRED_AFTER, combine_strict(s1, s2))]
  elif stem == PRED_BETWEEN:
    return [(PRED_AFTER, s1),
            (PRED_BEFORE, s2)]
  elif stem == PRED_BEFORE:
    return [(PRED_BEFORE, combine_strict(-1, s1)),
            (PRED_BEFORE, combine_strict(s1, -1)),
            (PRED_BEFORE, combine_strict(s1, -1)),
            (PRED_BEFORE, s1)]
  elif stem == PRED_AFTER:
    return [(PRED_AFTER, combine_strict(s1, -1)),
            (PRED_AFTER, combine_strict(-1, s1)),
            (PRED_AFTER, s1),
            (PRED_AFTER, combine_strict(-1, s1))]
  

def compare_results(res, res1):
  if not res or res == res1:
    return res1
  elif res1 == REL_DISJOINT:
    return REL_DISJOINT
  elif res == REL_EQUIVALENT:
    return res1
  elif res1 == REL_EQUIVALENT:
    return res
  elif ((res == REL_SUBSUMES and res1 == REL_SUBSUMED) or
        (res == REL_SUBSUMED and res1 == REL_SUBSUMES)):
    return REL_INTERSECTS
  elif res == REL_INTERSECTS or res1 == REL_INTERSECTS:
    return REL_INTERSECTS
  else:
    return REL_UNKNOWN
  

def split_and_compare(stem1, s1, s2, stem2, t1, t2):
  """Use determine-split to split the relations requested and use them to determine the relationship between the given predicates."""
  sp1 = determine_split(stem1, s1, s2)
  sp2 = determine_split(stem2, t1, t2)
  res = None
  for item1 in sp1:
    item2 = sp2[0]
    res1 = compare_single(item1[0], item1[1], item2[0], item2[1])
    sp2 = sp2[1:]
    res = compare_results(res, res1)
    if res == REL_DISJOINT:
      return res
  return res


def compare_pred_parts(stem1, s1, s2, stem2, t1, t2):
  """Compare two predicates which have been split into stems and strictness values."""
  if stem1 in PREDS_BETWEEN and stem2 in PREDS_BETWEEN:
    return split_and_compare(stem1, s1, s2, stem2, t1, t2)
  elif stem1 not in PREDS_BETWEEN and stem2 not in PREDS_BETWEEN:
    return split_and_compare(stem1, s1, s2, stem2, t1, t2)
  else:
    return REL_UNKNOWN


def compare_time_preds(pred1, pred2):
  """Return the relationship that holds between `pred1` and `pred2`.
  
  This relationship will be one of the following:

    - equivalent
    - subsumes
    - subsumed
    - disjoint
    - intersects
    - unknown
  """
  stem1, s1, s2 = split_time_pred(pred1)
  stem2, t1, t2 = split_time_pred(pred2)
  return compare_pred_parts(stem1, s1, s2, stem2, t1, t2)


def test_result(test, s1, s2, result, r1, r2):
  """Test whether the requested relation and the actual relation are compatible.
  
  Returns True, False, or None (for unknown).
  """
  comp = compare_pred_parts(test, s1, s2, result, r1, r2)
  if comp in [REL_EQUIVALENT, REL_SUBSUMES]:
    return True
  elif comp in [REL_DISJOINT]:
    return False
  elif comp in [REL_INTERSECTS, REL_SUBSUMED]:
    return None
  else:
    return None


def test_point_result(test, s1, result, r1):
  """The same as ``test_result``, except that the relations are assumed to be between points only."""
  comp = compare_single(test, s1, result, r1)
  if comp in [REL_EQUIVALENT, REL_SUBSUMES]:
    return True
  elif comp in [REL_DISJOINT]:
    return False
  elif comp in [REL_INTERSECTS, REL_SUBSUMED]:
    return None
  else:
    return None


def test_answer(reln, result):
  """Return whether `result` is acceptable for `reln` (or None if not known)."""
  if result == PRED_UNKNOWN:
    return result
  stem1, s1, s2 = split_time_pred(reln)
  stem2, t1, t2 = split_time_pred(result)
  return test_result(stem1, s1, s2, stem2, t1, t2)


def test_point_answer(reln, result):
  """The same as ``test_answer``, except that the relations are assumed to be between points only."""
  if result == PRED_UNKNOWN:
    return result
  stem1, s1, _ = split_time_pred(reln)
  stem2, t1, _ = split_time_pred(result)
  return test_point_result(stem1, s1, stem2, t1)


def combine_test_results(*tests):
  """Take the result of a number of tests and determine the "and"-ed result."""
  if None in tests:
    return False
  elif False in tests:
    return False
  elif REL_UNKNOWN in tests:
    return REL_UNKNOWN
  else:
    return True