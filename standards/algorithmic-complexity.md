# Algorithmic Complexity

## Data Structure Selection

Choose the structure that matches the dominant operation. A wrong choice turns O(1) lookups into O(n) scans.

### Decision Guide

| Need | Use | Avoid | Why |
|:-----|:----|:------|:----|
| Lookup by key | `Map` / `HashMap` | Array + `.find()` | Map: O(1) avg. Array scan: O(n) |
| Check membership | `Set` / `HashSet` | Array + `.includes()` | Set: O(1) avg. Array: O(n) |
| Ordered iteration by key | `TreeMap` / sorted array | HashMap | TreeMap: O(log n) insert, O(n) iteration in order. HashMap has no order |
| FIFO processing | Queue / `Deque` | Array + `.shift()` | `.shift()` is O(n) because it reindexes. Queue: O(1) |
| LIFO processing | Stack / array + `.push()`/`.pop()` | Linked list | Array push/pop: O(1). Cache-friendly |
| Frequent insert/delete at both ends | `Deque` / doubly-linked list | Array | Array shift/unshift: O(n). Deque: O(1) |
| Priority ordering | Min/max heap / priority queue | Sorted array + re-sort | Heap insert: O(log n). Re-sorting: O(n log n) |
| Range queries, nearest neighbor | Balanced BST / B-Tree / KD-Tree | Hash table | Hash tables do not support range queries |
| Counting occurrences | `Map<T, number>` | Nested loops | Map: O(n) single pass. Nested loops: O(n^2) |
| Deduplication | `Set` | `.filter()` + `.indexOf()` | Set: O(n). filter+indexOf: O(n^2) |

### Operation Complexity Reference

Average case. Worst case in parentheses when different.

| Structure | Access | Search | Insert | Delete | Space |
|:----------|:------:|:------:|:------:|:------:|:-----:|
| Array | O(1) | O(n) | O(n) | O(n) | O(n) |
| Stack | O(n) | O(n) | O(1) | O(1) | O(n) |
| Queue | O(n) | O(n) | O(1) | O(1) | O(n) |
| Linked List | O(n) | O(n) | O(1) | O(1) | O(n) |
| Hash Table | -- | O(1) (O(n)) | O(1) (O(n)) | O(1) (O(n)) | O(n) |
| BST | O(log n) (O(n)) | O(log n) (O(n)) | O(log n) (O(n)) | O(log n) (O(n)) | O(n) |
| Balanced BST | O(log n) | O(log n) | O(log n) | O(log n) | O(n) |
| B-Tree | O(log n) | O(log n) | O(log n) | O(log n) | O(n) |
| Skip List | O(log n) (O(n)) | O(log n) (O(n)) | O(log n) (O(n)) | O(log n) (O(n)) | O(n log n) |
| Heap | O(1) peek | O(n) | O(log n) | O(log n) | O(n) |
| Trie | O(k) | O(k) | O(k) | O(k) | O(n * k) |

`k` = key length for tries.

## Sorting Algorithm Selection

Most languages ship a well-optimized general sort (Timsort in Python/JS, introsort in C++). Use the built-in sort by default. Only reach for a specialized algorithm when you have a specific reason.

| When | Use | Complexity | Space | Why |
|:-----|:----|:-----------|:-----:|:----|
| General purpose | Built-in sort (Timsort) | O(n log n) worst | O(n) | Optimized for real-world data: fast on partially sorted input, stable |
| Nearly sorted data | Insertion sort | O(n) best | O(1) | Timsort already handles this. Manual insertion sort only for tiny arrays (<20 elements) |
| Integer/fixed-range keys | Counting sort / Radix sort | O(n + k) / O(n * d) | O(k) / O(n + k) | Linear time when key range is bounded. Not comparison-based |
| Memory constrained | Heapsort | O(n log n) | O(1) | In-place, guaranteed worst case. Not stable |
| External data (disk) | External merge sort | O(n log n) | O(n) | Designed for data that does not fit in memory |
| Stability required | Merge sort / Timsort | O(n log n) | O(n) | Preserves relative order of equal elements |

### Sorting Anti-Patterns

- Sorting when you only need the min/max/k-th element. Use a heap or `quickselect` (O(n) average) instead of sorting (O(n log n))
- Sorting inside a loop. Sort once outside, then iterate
- Sorting to find duplicates. Use a Set (O(n)) instead
- Sorting to check membership. Use a Set or Map (O(1) lookup) instead
- Re-sorting after a single insertion. Use a binary search + splice or a sorted data structure

## Complexity Classification

| Class | Name | Scale behavior | Acceptable for |
|:------|:-----|:---------------|:---------------|
| O(1) | Constant | Instant at any scale | Anything |
| O(log n) | Logarithmic | Barely grows (1B items = ~30 steps) | Anything |
| O(n) | Linear | Grows proportionally | Single-pass operations, data under ~10M items |
| O(n log n) | Linearithmic | Sorting territory | Sorting, divide-and-conquer on moderate data |
| O(n^2) | Quadratic | 10x data = 100x time | Only for n < 1,000. Flag in code review for anything larger |
| O(n^3) | Cubic | 10x data = 1,000x time | Only for n < 100. Matrix operations with no better algorithm |
| O(2^n) | Exponential | Doubles with each element | Only for n < 25. Subset/combination problems without pruning |
| O(n!) | Factorial | Unusable past n=12 | Only for n < 12. Permutation problems without pruning |

### Practical Thresholds

These are rough ceilings for interactive applications (sub-second response). Batch processing and background jobs have higher tolerance.

| Complexity | Safe n for ~100ms | Safe n for ~1s |
|:-----------|:-----------------:|:--------------:|
| O(n) | ~10M | ~100M |
| O(n log n) | ~1M | ~10M |
| O(n^2) | ~1,000 | ~10,000 |
| O(n^3) | ~100 | ~500 |
| O(2^n) | ~20 | ~25 |

These depend on constant factors, hardware, and language. Measure before assuming.

## Complexity Analysis Rules

How to identify the complexity of code during review.

### Loops

| Pattern | Complexity | Example |
|:--------|:-----------|:--------|
| Single loop over n items | O(n) | `for (const x of items)` |
| Nested loop, both over n | O(n^2) | `items.forEach(a => items.forEach(b => ...))` |
| Loop with halving step | O(log n) | `while (lo < hi) { mid = (lo+hi)/2; ... }` |
| Loop inside a loop where inner is O(log n) | O(n log n) | `items.forEach(x => binarySearch(sorted, x))` |
| Three nested loops over n | O(n^3) | Matrix multiplication |
| Loop that processes then removes (shrinking input) | O(n^2) | `.shift()` in a while loop |

### Method Chains

Chained array methods look clean but multiply. Each `.filter()`, `.map()`, `.reduce()`, `.find()`, `.some()` is O(n). Chaining k of them is O(k * n), not O(n).

When chained operations are independent (filter then map), O(k * n) is still linear and acceptable. The danger is chaining inside a loop:

```typescript
// O(n^2): .find() is O(n), called n times
users.map(user => orders.find(o => o.userId === user.id));

// O(n): build a Map first, then look up in O(1)
const ordersByUser = new Map(orders.map(o => [o.userId, o]));
users.map(user => ordersByUser.get(user.id));
```

### Recursion

| Pattern | Complexity | Example |
|:--------|:-----------|:--------|
| Single branch, n shrinks by 1 | O(n) | Factorial, linked list traversal |
| Single branch, n halves each call | O(log n) | Binary search |
| Two branches, n shrinks by 1 | O(2^n) | Naive Fibonacci, subset generation |
| Two branches, n halves each call | O(n) | Merge sort (combine step is O(n)) |
| k branches, n shrinks by 1 | O(k^n) | Backtracking without pruning |

**Master theorem shortcut** for `T(n) = a * T(n/b) + O(n^d)`:
- If d < log_b(a): O(n^(log_b(a)))
- If d = log_b(a): O(n^d * log n)
- If d > log_b(a): O(n^d)

### Amortized Complexity

Some operations are expensive occasionally but cheap on average. Dynamic array `.push()` is O(1) amortized: most pushes are O(1), but when the array doubles its capacity, that single push is O(n). Over n pushes, total work is O(n), so each push is O(1) amortized.

Common amortized O(1) operations:
- Dynamic array append (ArrayList, Vec, JS Array push)
- Hash table insert (when load factor is managed)
- Splay tree access (O(log n) amortized over a sequence)

Amortized cost matters for throughput. Worst-case cost matters for latency. If a single slow operation is unacceptable (real-time systems, request handlers with SLOs), use the worst-case bound.

## Common Anti-Patterns

Patterns that hide quadratic or worse complexity behind innocent-looking code.

| Anti-pattern | Hidden cost | Fix |
|:-------------|:-----------|:----|
| `.find()` / `.includes()` inside `.map()` / `.forEach()` | O(n^2) | Build a Map or Set first, then look up |
| `.filter().length === 0` to check emptiness | O(n) | Use `.some()` or `.every()` for early exit |
| `Array.from(set).sort()` for sorted unique values | O(n log n) + O(n) allocation | Acceptable, but consider `SortedSet` if done repeatedly |
| `JSON.parse(JSON.stringify(obj))` for deep clone | O(n) with high constant: serialization + parsing + memory | `structuredClone(obj)` is faster and handles more types |
| String concatenation in a loop | O(n^2) total: each concat copies the growing string | Collect in array, `.join()` at the end |
| `Array.shift()` in a while loop | O(n^2): each shift reindexes the entire array | Use a queue, pointer index, or reverse + pop |
| Nested `.reduce()` with spread accumulator | O(n^2): spread copies the accumulator on every iteration | Mutate the accumulator inside reduce, or use a loop |
| `delete obj[key]` in V8 | Transitions object to slow "dictionary mode" | Set to `undefined` or use a `Map` |
| Regex with catastrophic backtracking | O(2^n) for pathological input | Avoid nested quantifiers on overlapping patterns. Use linear-time regex engines for user input |
| Recursive Fibonacci without memoization | O(2^n) | Memoize (O(n) time, O(n) space) or use iteration (O(n) time, O(1) space) |

## Space Complexity

Time gets measured. Space gets forgotten. Then the OOM kill arrives.

### Common Memory Costs

| Pattern | Space | Risk |
|:--------|:------|:-----|
| Accumulating results in an array | O(n) | Unbounded if n is unknown. Stream or paginate instead |
| Recursive call stack | O(depth) | Stack overflow on deep recursion. Use iteration with explicit stack |
| Memoization / caching | O(unique inputs) | Unbounded without eviction. Add TTL, LRU, or max size |
| Closures capturing outer scope | O(captured vars) | Closures in long-lived objects (event handlers, timers) prevent GC of captured variables |
| `.map()` / `.filter()` chains | O(n) per step | Each step allocates a new array. For large datasets, use a single loop or generators |
| Buffering entire HTTP response | O(response size) | Stream large responses. Set body size limits |
| Event listener accumulation | O(listeners) | Listeners registered in loops or hot paths without cleanup. Use `AbortController` or cleanup in `useEffect` return |
| Object spread in reduce | O(n^2) total | Each spread copies the growing object. Mutate the accumulator instead |

### Space Optimization Strategies

- **Stream instead of buffer**: process data as it arrives instead of loading it all into memory
- **Generators instead of arrays**: `function*` yields one item at a time, O(1) working memory
- **Bounded caches**: every cache must have a max size and eviction policy. No unbounded `Map` used as cache
- **WeakMap / WeakRef**: for caches keyed by objects. Entries are GC'd when the key is GC'd
- **Pool and reuse**: for expensive objects (buffers, connections), reuse from a pool instead of allocating per request
- **Pagination at every boundary**: database queries, API responses, file reads. Never load "all" without a limit
