# Low-Latency Engineering

On-demand standard. Loaded when a task touches HFT, embedded real-time, kernel-adjacent latency-critical code, or any scenario where nanoseconds and microseconds determine correctness. Not loaded for typical web or backend work; for those, see [`performance.md`](performance.md) and [`performance-budgets.md`](performance-budgets.md).

## When This Standard Applies

| Domain | Apply? |
|--------|--------|
| High-frequency trading order-path code | Yes |
| Market-data ingestion under microsecond budgets | Yes |
| Real-time signal processing, audio DSP, robotics control loops | Yes |
| Embedded systems with hard-real-time deadlines | Yes |
| Kernel modules, drivers, network stacks | Yes |
| Web API latency tuning | No, use [`performance.md`](performance.md) |
| Bundle size and Core Web Vitals | No, use [`performance.md`](performance.md) |
| Database query optimization | No, use [`database.md`](database.md) |

## Foundational Premise

Linux is a soft real-time system. The scheduler aims for fairness and throughput, not deterministic deadlines. A process can be ready to run for tens of microseconds while the kernel handles an interrupt, services another task, or stalls in a system management routine. Code that runs in 50 nanoseconds in isolation can finish 80 microseconds later in production. The job of low-latency engineering is to remove every source of jitter from the critical path.

## Memory Hierarchy

### Translation Lookaside Buffer (TLB)

Every memory access goes through virtual-to-physical address translation. The CPU caches recent translations in the TLB. A TLB miss triggers a page-table walk in RAM that costs 100 to 200 times more than the cached path in nanoseconds.

Default 4 KB pages exhaust TLB capacity on large heaps. A 32 GB heap needs 8 million 4 KB pages; the TLB holds far fewer entries. Cold paths and large working sets miss constantly.

Mitigation: hugepages.

| Page size | Entries for 32 GB | Notes |
|-----------|-------------------|-------|
| 4 KB default | 8,388,608 | Cold paths thrash the TLB |
| 2 MB | 16,384 | Default hugepage size on Linux |
| 1 GB | 32 | Requires `default_hugepagesz=1G` boot parameter |

Implementation:

```c
// C++: pass MAP_HUGETLB to mmap
void *p = mmap(NULL, size, PROT_READ | PROT_WRITE,
               MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB | MAP_HUGE_1GB,
               -1, 0);
if (p == MAP_FAILED) { /* handle */ }
```

```rust
// Rust: memmap2 or hugepage-rs crates
use memmap2::MmapOptions;
let mmap = MmapOptions::new()
    .len(size)
    .huge(Some(30)) // 2^30 = 1 GB
    .map_anon()?;
```

### Memory Pinning

Lazy page mapping persists even with hugepages. The kernel maps pages on first access, which faults into the kernel. `mlockall` eagerly maps every page and pins them against swap before the latency-critical section begins.

```c
#include <sys/mman.h>
if (mlockall(MCL_CURRENT | MCL_FUTURE) != 0) { /* handle */ }
```

```rust
unsafe {
    if libc::mlockall(libc::MCL_CURRENT | libc::MCL_FUTURE) != 0 {
        panic!("mlockall failed");
    }
}
```

Run `mlockall` before entering the hot loop. Check `RLIMIT_MEMLOCK` ahead of time; the system default is often too low and the call silently fails on some kernels.

## NUMA

Multi-socket servers have per-socket memory pools. A thread running on socket 0 reading memory allocated on socket 1 pays an interconnect cost of 100 to 200 nanoseconds extra per access.

### Allocation Policies

| Policy | Behavior | Use for HFT? |
|--------|----------|--------------|
| Local default | Allocate on the node the thread runs on | No, depends on initial scheduling |
| Bind | Restrict allocation to specified nodes | Yes |
| Preferred | Try one node, fall back to others | No, fallback adds jitter |
| Interleave | Spread allocations across nodes | No, intentionally non-local |

### Discovery

```bash
numactl --hardware   # node count and per-node memory
lscpu                 # CPU topology
lstopo                # tree view with cache levels
```

### Pinning

```bash
numactl --cpunodebind=0 --membind=0 ./trading-engine
taskset -c 2,3 ./trading-engine   # specific cores within a node
```

### Disable Auto-Migration

Linux `autonuma` migrates pages between nodes based on observed access patterns. Useful for fairness, fatal for latency.

```bash
# sysctl
echo 0 > /proc/sys/kernel/numa_balancing

# Boot parameter (persistent)
GRUB_CMDLINE_LINUX_DEFAULT="... numa_balancing=disable"
```

### Verification

```bash
numastat -p <PID>     # per-process memory distribution
numastat -m           # system-wide
```

Runtime verification in code uses `libnuma`. Check `numa_node_of_cpu()` against `numa_node_of_addr()` to confirm allocation locality before entering the hot path.

## Scheduling and Jitter

### Priority

```bash
chrt --pid --fifo 99 <PID>   # SCHED_FIFO at maximum priority
```

SCHED_FIFO runs to completion or until a higher-priority task preempts. Use SCHED_FIFO 99 only on threads that never block on I/O. A blocked FIFO thread holding a kernel resource starves the rest of the system.

### Hard IRQs

Network cards, disks, and timers interrupt whichever core handles them. Move every non-essential IRQ off the trading core.

```bash
# Discover IRQ numbers
cat /proc/interrupts

# Pin IRQ N to core 0 (binary mask: bit 0 = core 0)
echo 1 > /proc/irq/<N>/smp_affinity
```

Reserve the trading cores via the kernel boot parameter `isolcpus=2,3,4,5` and route all IRQs to the housekeeping cores 0 and 1.

### Non-Maskable Interrupts (NMI)

The watchdog NMI fires periodically to detect kernel lockups. It cannot be deferred and pauses every core briefly.

```bash
sysctl -w kernel.nmi_watchdog=0
```

Persist via `GRUB_CMDLINE_LINUX_DEFAULT="... nmi_watchdog=0"`.

### System Management Interrupts (SMI)

BIOS-sourced interrupts handle thermal throttling, power management, and ECC scrubbing. SMI handlers run outside OS visibility and can pause every core for 100 microseconds or more.

On server-class hardware, disable in BIOS:

- Global SMI handlers
- All C-states beyond C0/C1
- Hardware power management
- Memory scrubbing if the system supports ECC reporting

This requires server-class firmware. Consumer motherboards typically expose none of these settings.

### Software Faults

Page faults and TLB misses jump into the kernel. The mitigations are above: hugepages plus `mlockall`. After applying both, the only remaining software faults during steady-state should be CPU exceptions in the trading code itself, which the design must eliminate.

## Validation Tools

| Tool | What it measures | Trading-acceptable threshold |
|------|------------------|------------------------------|
| `cyclictest` | Scheduler wake-up latency | Max < 10 microseconds on a tuned system |
| `hwlatdetect` | Hardware-induced latency from NMI and SMI | Zero detections over 24 hours |
| `numastat` | Per-process memory locality | 100 percent on the bound node |
| `perf record` | CPU events including TLB misses and cache misses | TLB miss rate < 0.1 percent on hot paths |
| `bpftrace` | Custom kernel tracing | Zero unexpected events on the hot path |

Run `cyclictest -m -p99 -i100 -h100` against the trading core during burn-in. Record the 99.9th percentile.

## Pre-Production Checklist

Before deploying any latency-sensitive code to production:

1. Hugepages allocated and visible in `/proc/meminfo` (`HugePages_Total`).
2. `mlockall` returns 0 at startup; verify under `RLIMIT_MEMLOCK=unlimited`.
3. `numa_balancing` is 0.
4. Trading threads run on `isolcpus` cores.
5. All non-essential IRQs routed away from trading cores.
6. `nmi_watchdog` is 0.
7. C-states beyond C1 disabled in BIOS.
8. `cyclictest` baseline recorded, max wake-up latency under target.
9. `hwlatdetect` shows zero hardware latency events over the burn-in window.
10. `numastat` shows 100 percent local allocation under load.

## Cross-References

- [`performance.md`](performance.md) for web-stack and frontend performance.
- [`performance-budgets.md`](performance-budgets.md) for SLO and budget framing.
- [`algorithmic-complexity.md`](algorithmic-complexity.md) for the algorithm-level analysis that runs before any of this matters.
