# JVM (Java and Kotlin)

Standards for code targeting the Java Virtual Machine. Applies to Java 17+ and Kotlin 1.9+.

## Build and Tooling

- Gradle (Kotlin DSL) is preferred over Maven for new projects; both are acceptable for existing ones
- Pin the JDK version with `toolchain` in Gradle. Don't rely on `JAVA_HOME`
- Treat compiler warnings as errors: `-Werror` for javac, `allWarningsAsErrors = true` for Kotlin
- Run Spotless or ktlint on every commit; CI fails on formatting drift

## Strictness

| Tool | Setting |
|------|---------|
| Java compiler | `-Xlint:all -Werror` |
| Kotlin compiler | `-Werror`, `-progressive`, `-Xexplicit-api=strict` for libraries |
| Linters | Detekt for Kotlin, SpotBugs and PMD for Java, Error Prone for Java |
| Static analysis | Checker Framework (Java) for null and immutability checks |

## Null Handling

- Java: prefer `Optional<T>` for return values, never for parameters or fields. Annotate with JSpecify (`@Nullable`, `@NonNull`) for tooling
- Kotlin: nullable types are part of the type system. Use `!!` only when a runtime invariant is documented; never for hopeful access

## Immutability

- Java records for value types (Java 14+)
- Kotlin `data class` with `val` properties; copy with `copy()`
- Collections: `List.of(...)`, `Set.of(...)`, `Map.of(...)` for immutable instances. Avoid `Collections.unmodifiableList` wrappers when a true immutable factory exists
- Kotlin: `listOf`, `setOf`, `mapOf` for read-only views; `persistentListOf` (kotlinx.collections.immutable) for structurally immutable

## Concurrency

- Virtual threads (Project Loom, Java 21+) for blocking I/O. Spawn liberally; they're cheap
- Kotlin coroutines: structured concurrency through `coroutineScope`, `supervisorScope`. Never `GlobalScope`
- `CompletableFuture` for async pipelines in plain Java. Always supply a custom `Executor` for production code
- Lock with `ReentrantLock` over `synchronized` when fairness or interruption matters

## Resource Management

- `try-with-resources` for any `AutoCloseable`
- Kotlin: `use { }` extension function on closeables
- Never leak `InputStream`, `Connection`, `Channel`. Wrap in try-with-resources at the call site

## Exception Handling

- Don't catch `Exception` or `Throwable` except at framework boundaries
- Checked exceptions in Java public APIs only when callers can meaningfully recover
- Kotlin has no checked exceptions; document failure modes in KDoc
- Wrap and rethrow: `throw new MyException("context", cause)`. Never swallow

## Spring and Frameworks

- Constructor injection only. No `@Autowired` field injection
- `@ConfigurationProperties` over scattered `@Value` annotations
- Profile-specific beans via `@Profile`, not runtime conditionals
- Reactive (`Mono`, `Flux`) when the workload is I/O-bound and high-concurrency; imperative otherwise

## Testing

- JUnit 5 (`org.junit.jupiter.api.Test`)
- AssertJ for fluent assertions over JUnit's built-in `assertEquals`
- Mockito for mocks, but prefer real collaborators when feasible
- Testcontainers for database, message broker, and dependency tests
- Kotest for property-based testing in Kotlin

## Performance

- JIT warmup matters: discard the first few iterations in benchmarks
- Use JMH for microbenchmarks; never `System.nanoTime()` loops
- GC tuning: G1 is the default for most workloads. ZGC for low-latency requirements
- Profile with async-profiler or Java Flight Recorder; never assume

## Module System (Java)

- For libraries, use the module system (`module-info.java`) to declare exposed packages
- Don't `requires transitive` unless callers genuinely need the transitive type
- Multi-module Gradle projects: prefer convention plugins over copy-paste build scripts
