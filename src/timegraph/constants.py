from datetime import date

PSEUDO_INIT = 1
"""int: pseudo time for the first element on the chain."""

PSEUDO_INCREMENT = 1000
"""int: pseudo time increment between nodes."""

POINT_LINK_PAIRS = {
  'descendants' : 'ancestors',
  'ancestors' : 'descendants',
  'xdescendants' : 'xancestors',
  'xancestors' : 'xdescendants'
}
"""dict[str, str]: a list of all possible links between TimePoint objects, and the opposite link type for each."""



# ``````````````````````````````````````
# Absolute time
# ``````````````````````````````````````



DATETIME_ARGS = ['year', 'month', 'day', 'hour', 'minute', 'second']
"""list[str]: all supported datetime arguments for absolute times, in order."""

DATETIME_REQUIRED_ARGS = ['year', 'month', 'day']
"""list[str]: Mandatory arguments for the datetime class."""

DATETIME_LOWER = {
  'year' : 1,
  'month' : 1,
  'day' : 1,
  'hour' : 0,
  'minute' : 0,
  'second' : 0
}
"""dict[str, int]: The lowest possible values for each datetime argument."""

DATETIME_UPPER = {
  'year' : date.today().year,
  'month' : 12,
  'day' : 31,
  'hour' : 23,
  'minute' : 59,
  'second' : 59
}
"""dict[str, int]: The greatest possible values for each datetime argument."""



# ``````````````````````````````````````
# Predicates
# ``````````````````````````````````````



PRED_EQUAL = 'equal'
PRED_SAME_TIME = 'same-time'
PRED_AT = 'at'
PRED_EXACTLY = 'exactly'
PREDS_EQUIV = [PRED_EQUAL, PRED_SAME_TIME, PRED_AT, PRED_EXACTLY]

PRED_BEFORE = 'before'
PRED_AFTER = 'after'
PREDS_SEQ = [PRED_BEFORE, PRED_AFTER]

PRED_DURING = 'during'
PRED_CONTAINS = 'contains'
PRED_OVERLAPS = 'overlaps'
PRED_OVERLAPPED_BY = 'overlapped-by'
PREDS_CONTAINMENT = [PRED_DURING, PRED_CONTAINS, PRED_OVERLAPS, PRED_OVERLAPPED_BY]

PRED_BETWEEN = 'between'
PREDS_BETWEEN = [PRED_BETWEEN]

PRED_AT_MOST_BEFORE = 'at-most-before'
PRED_AT_LEAST_BEFORE = 'at-least-before'
PRED_EXACTLY_BEFORE = 'exactly-before'
PREDS_CONSTRAINED_BEFORE = [PRED_AT_MOST_BEFORE, PRED_AT_LEAST_BEFORE, PRED_EXACTLY_BEFORE]

PRED_AT_MOST_AFTER = 'at-most-after'
PRED_AT_LEAST_AFTER = 'at-least-after'
PRED_EXACTLY_AFTER = 'exactly-after'
PREDS_CONSTRAINED_AFTER = [PRED_AT_MOST_AFTER, PRED_AT_LEAST_AFTER, PRED_EXACTLY_AFTER]

PRED_UNKNOWN = 'unknown'

PREDS_1 = PREDS_EQUIV + PREDS_SEQ + PREDS_CONTAINMENT
PREDS_2 = PREDS_BETWEEN
PREDS_3 = PREDS_CONSTRAINED_BEFORE + PREDS_CONSTRAINED_AFTER

PREDS = PREDS_1 + PREDS_2 + PREDS_3 + [PRED_UNKNOWN]
"""list[str]: All possible predicate stems."""

INVERSE_PREDS = {
  PRED_BEFORE : PRED_AFTER,
  PRED_AFTER : PRED_BEFORE,
  PRED_DURING : PRED_CONTAINS,
  PRED_CONTAINS : PRED_DURING,
  PRED_OVERLAPS : PRED_OVERLAPPED_BY,
  PRED_OVERLAPPED_BY : PRED_OVERLAPS
}
"""dict[str, str]: Mappings from particular predicate stems to their inverses."""



# ``````````````````````````````````````
# Predicate relations
# ``````````````````````````````````````



REL_EQUIVALENT = 'equivalent'
REL_DISJOINT = 'disjoint'
REL_SUBSUMES = 'subsumes'
REL_SUBSUMED = 'subsumed'
REL_INTERSECTS = 'intersects'
REL_UNKNOWN = 'unknown'

RELS = [REL_EQUIVALENT, REL_DISJOINT, REL_SUBSUMES, REL_SUBSUMED, REL_INTERSECTS, REL_UNKNOWN]
"""list[str]: All possible relations between predicates."""
