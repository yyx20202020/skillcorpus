# Bounded Queues and Backpressure Primer

An original SkillCorpus fixture (MIT). Not derived from any copyrighted book.

## Chapter 1 — Why Bound the Queue

A **bounded queue** rejects or slows producers when capacity is full.
Without a bound, memory grows until the process dies. Prefer a clear
backpressure signal over silent buffering.

In Chinese: 有界队列在容量耗尽时必须施加背压（backpressure），而不是无限缓冲。

## Chapter 2 — Drop vs Block vs Sample

Choose a policy when the queue is full:

| Policy | When to use |
|--------|-------------|
| Block producer | Local threads, latency may rise |
| Drop-new | Telemetry where newest matters less |
| Drop-old | Dashboards that need fresh samples |
| Sample | High-cardinality event streams |

Rule of thumb: **never pretend a write succeeded if it was dropped**.

## Chapter 3 — Code Sketch

```python
class BoundedQueue:
    def __init__(self, capacity: int):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._items = []

    def push(self, item):
        if len(self._items) >= self.capacity:
            return False  # backpressure signal
        self._items.append(item)
        return True
```

The `False` return is the backpressure signal. Callers must handle it.

## Chapter 4 — Measuring Pressure

Track `queue_depth / capacity`. Alert when the ratio stays above 0.8 for
more than one minute. Pair with producer wait time and drop counts.

## Chapter 5 — Anti-Patterns

- Unlimited `list.append` in request handlers
- Swallowing drop events without metrics
- Mixing multiple unrelated workloads into one shared unbounded buffer
