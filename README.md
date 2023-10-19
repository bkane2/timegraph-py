# Python Timegraph

Python library for computing temporal relations between temporally-bounded events using the timegraph algorithm [[1,2]](#references).

A timegraph is a directed, acyclic graph whose vertices represent single points in time, and whose edges represent a ≤ ("before or at") relationship. Each event corresponds to two points in the timegraph: one representing the beginning of the episode, and one representing the end of the episode (with the first coming before the second).



## Dependencies



## Summary

Install the package using `pip install timegraph`.

Import the package using the following line.

```python
from timegraph import timegraph
```

TODO


## Documentation

TODO


## References

* [1] Taugher J. [An efficient representation for time information](https://era.library.ualberta.ca/items/1e8a8293-e36e-4d75-9855-b3981ef4dd9c). M.<span></span>Sc. thesis, Department of Computing Science, University of Alberta, Edmonton, AB., 1983.

* [2] Gerevini A.; Schubert L. K.; Schaeffer S. [The temporal reasoning tools TimeGraph-I-II](https://ieeexplore.ieee.org/document/346448) Proc. of the 6th IEEE Int. Conf. on Tools with Artificial Intelligence, Nov. 6-9, New Orleans, Louisiana, 1994.