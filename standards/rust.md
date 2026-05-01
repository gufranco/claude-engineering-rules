# Rust

## Compiler Strictness

- `#![deny(warnings)]` in `lib.rs` and binaries
- `clippy::pedantic` in CI; selectively allow noisy lints in code with rationale
- `cargo deny` for license, advisory, and duplicate dependency checks
- `rust-toolchain.toml` pins the toolchain so every contributor builds the same way

## Ownership and Lifetimes

- Prefer borrowing over cloning. `&str` over `String`, `&[T]` over `Vec<T>` in function signatures
- Return owned types when transferring ownership; borrow when the caller keeps the value
- Avoid `Rc<RefCell<T>>` until profiling proves shared mutability is required
- Use lifetime elision when the compiler can infer; name lifetimes only when ambiguity forces it

## Error Handling

- Library crates: define a typed error enum with `thiserror`. One enum per crate
- Application crates: use `anyhow` for opaque, context-rich errors at boundaries
- Never `.unwrap()` outside tests, examples, or genuinely impossible-to-fail paths. `expect("reason")` is acceptable when the assumption is documented
- Prefer `?` propagation. Use `map_err` to attach context

## Async

- Pick one runtime per workspace (Tokio is the default). Mixing causes runtime panics
- Spawn tasks with `tokio::spawn`; never `std::thread::spawn` for async work
- Hold locks across `.await` only when the lock is async-aware (`tokio::sync::Mutex`); std `Mutex` deadlocks under task scheduling
- Cancellation safety: every `.await` may be cancelled. Avoid partial state mutations between awaits

## Performance

- `cargo build --release` for benchmarks. Debug builds are 10-100x slower
- Use `Cow<str>` when a function sometimes borrows and sometimes owns
- `Box<dyn Trait>` for dynamic dispatch; generics for monomorphized code paths. Prefer generics in hot paths
- Profile with `cargo flamegraph` or `perf` before micro-optimizing

## Unsafe

- `unsafe` blocks require a `// SAFETY:` comment explaining the invariants the caller must uphold
- Encapsulate `unsafe` behind safe abstractions; never expose raw pointers to library consumers
- Run `cargo miri` on test suites that exercise `unsafe` code

## Testing

- Unit tests in `#[cfg(test)] mod tests` at the bottom of the module
- Integration tests in `tests/` directory; each file is a separate crate
- Property-based tests with `proptest` for parser, math, and serialization code
- `#[should_panic(expected = "...")]` to assert panic messages

## Tooling

| Tool | Purpose |
|------|---------|
| `cargo fmt` | Formatter, run before every commit |
| `cargo clippy` | Linter |
| `cargo test --all-features` | Run tests across feature flags |
| `cargo doc --no-deps` | Generate documentation; check for broken links |
| `cargo audit` | RustSec advisory database scan |
| `cargo machete` | Find unused dependencies |
