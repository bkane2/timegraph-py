# Python Timegraph

Python package for efficiently storing and computing temporal relations between temporally-bounded events using the timegraph algorithm [[1,2]](#references).

A timegraph is a directed, acyclic graph whose vertices represent single points in time, and whose edges represent either a ≤ ("before or at") or < ("strictly before") relationship. To improve efficiency, time points are maintained on several separate chains, which are connected to each other using cross-chain edges, forming a "metagraph". Each event corresponds to two points in the timegraph: one representing the beginning of the episode, and one representing the end of the episode (with the first coming before the second).

Absolute time bounds for time points (e.g., "from 11/3/2023 to 11/4/2023") are also supported, as well as minimum and maximum bounds on the durations between time points.

The implementation in this package is directly based on the time specialist in the [EPILOG program](https://www.cs.rochester.edu/research/epilog/), except modified for generic use.



## Summary

Install the package using `pip install timegraph`.

Import the package and instantiate an empty timegraph using the following line. No dependencies are required.

```python
from timegraph.timegraph import TimeGraph
from timegraph.abstime import AbsTime # if using absolute times
tg = TimeGraph()
```

The package exports the following functions (see the below sections for additional details on the parameters):


### Registering an event

If a particular symbol is to be interpreted as an event (i.e., an interval with time points for the start and end),
it first needs to be registered with the timegraph, or otherwise it will be interpreted as the name of a single timepoint.
To do this, use the following function:

```python
tg.register_event('e1')
tg.register_event('e2')
```


### Creating an absolute time

In order to set an absolute time bound for a time point or event, first create an absolute time object. The constructor for this class takes a 6-element list `[year, month, day, hour, minute, second]`. For example:

```python
t1 = AbsTime([1997, 7, 2, 1, 1, 1])
```

This absolute time can then be provided as an argument when calling the following functions (if supported). Additionally, an absolute time can contain a symbol/variable for a particular slot (e.g., if the exact day is unknown), though this may not be currently supported by all timegraph functions:

```python
t1 = AbsTime([1997, 7, 'd', 1, 1, 1])
```


### enter

In order to add a new temporal relation to the timegraph (creating the relevant points as well, if they don't already exist),
the `enter` function should be used. It takes a temporal predicate along with 2 or 3 arguments, depending on the predicate.

```python
tg.enter('e1', 'before', 'e2')
```

Each predicate can be modified with a strictness value for either argument, separated by dashes, indicating whether the relation for that argument is strictly < or > (value of 1) or a "meets" relation (value of 0). By default, the strictness is -1, indicating <= or >= depending on the stem. For example:

```python
tg.enter('e1', 'before-1', 'e2')
tg.enter('e1', 'before-1-0', 'e2')
tg.enter('e1', 'before--1', 'e2')
```

The following basic predicates are supported:

#### Sequential relations
```python
tg.enter(x, 'before', y)
tg.enter(x, 'after', y)
```

Where `x` and `y` are either events or time points, or *at most one* is an absolute time.

#### Containment relations
```python
tg.enter(x, 'during', y)
tg.enter(x, 'contains', y)
tg.enter(x, 'overlaps', y)
tg.enter(x, 'overlapped-by', y)
```

Where `x` and `y` are either events or time points, or *at most one* is an absolute time.

#### Equality relations
```python
tg.enter(x, 'equal', y)
tg.enter(x, 'same-time', y) # synonymous with the previous relation
```

Where `x` and `y` are either events or time points, or *at most one* is an absolute time.

#### Between relation
```python
tg.enter(x, 'between', y, z)
```

Where `x`, `y`, and `z` are either events or time points, or *at most two* are absolute times.

#### Duration-constrained sequential relations
```python
tg.enter(x, 'at-most-before', y, dur)
tg.enter(x, 'at-least-before', y, dur)
tg.enter(x, 'exactly-before', y, dur)
tg.enter(x, 'at-most-after', y, dur)
tg.enter(x, 'at-least-after', y, dur)
tg.enter(x, 'exactly-after', y, dur)
```

Where `x` and `y` are either events or time points, and `dur` is a numerical duration.

#### Event duration relation
```python
tg.enter(x, 'has-duration', dur)
```

Where `x` is an event, and `dur` is a numerical duration.


### relation

The following function can be used to search for the strongest relation that holds between any two points (only binary relations are currently supported). Each argument may be either a time point or an event, or *at most one* may be an absolute time. The `effort` argument determines the effort to put into the search, by default 1 -- a value of 0 will make the search quicker, but less precise.

```python
tg.relation(x, y, effort=1)
```


### evaluate

The following function can be used to evaluate the truth of a relation between two or three points (for the same set of predicates as supported by `enter`). It returns `True`, `False`, or `None` for "unknown". The optional argument `negated` can also be supplied to negate the result of the predicate.

```python
tg.evaluate(x, 'after', y, effort=1)
tg.evaluate(x, 'between', y, z, effort=1, negated=True)
```


### start_of/end_of

The functions `start_of` and `end_of` can be used to obtain the symbols created in the timegraph for the start and end points of events:

```python
tg.get_start('e1') # -> 'e1start'
tg.get_end('e1') # -> 'e1end'
```


### elapsed

The following function can be used to get the minimum and maximum bounds on the duration between two time points or events in the timegraph:

```python
tg.elapsed(x, y, effort=1)
```


### duration

The following function can be used to get the minimum and maximum bounds on the duration of an event:

```python
tg.duration(x, effort=1)
```


## Documentation

The timegraph implementation is structured as follows:

#### constants.py

Contains constants used throughout the package, including default values and supported predicates/relations between predicates.

#### util.py

Contains generic utility functions used in the package.

#### pred.py

Contains functions for processing and comparing predicate symbols.

#### abstime.py

Contains the implementation of the `AbsTime` class for representing an absolute time.

#### timestructs.py

Contains the main structures used in the timegraph data structure:

* `TimePoint`: a time point (node in the timegraph), containing a pseudotime (and minimum/maximum bounds thereof), absolute time bounds, and adjacent time links.

* `TimeLink`: a link between two time points, with associated strictness value (0 or 1), containing stored bounds on the duration.

* `TimeLinkList`: a list of time links with a particular ordering on elements.

* `MetaNode`: a time chain, i.e., a node in the "metagraph", with a pointer to the first element of the chain and all cross-links to other chains.

* `EventPoint`: an event/interval with names for the start and end time points.

#### timegraph.py

The primary implementation of the timegraph object. Contains hash tables mapping each time point symbol to the corresponding node, each chain number to the corresponding meta node, and each event symbol to the corresponding event point.


## References

* [1] Taugher J. [An efficient representation for time information](https://era.library.ualberta.ca/items/1e8a8293-e36e-4d75-9855-b3981ef4dd9c). M.<span></span>Sc. thesis, Department of Computing Science, University of Alberta, Edmonton, AB., 1983.

* [2] Gerevini A.; Schubert L. K.; Schaeffer S. [The temporal reasoning tools TimeGraph-I-II](https://ieeexplore.ieee.org/document/346448) Proc. of the 6th IEEE Int. Conf. on Tools with Artificial Intelligence, Nov. 6-9, New Orleans, Louisiana, 1994.