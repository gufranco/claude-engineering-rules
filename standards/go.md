# Go

## Linting and Strictness

- `go vet ./...` plus `staticcheck` in CI
- `golangci-lint` with `errcheck`, `govet`, `staticcheck`, `gosec`, `revive`, `gocritic`
- `gofmt -s` and `goimports` enforced as part of pre-commit
- Build with `-trimpath` and `-ldflags="-buildid="` for reproducible binaries

## Error Handling

- Errors are values. Always check the `error` return; never assign to `_` without a reason
- Wrap errors with `fmt.Errorf("operation: %w", err)` to preserve the chain. Use `errors.Is`/`errors.As` to inspect
- Define typed sentinel errors at package level: `var ErrNotFound = errors.New("not found")`
- Don't log and return; either log or return, not both. Logging twice creates duplicate noise
- For domain errors, define a struct that implements `error` with structured fields

## Concurrency

- `context.Context` flows as the first parameter through all I/O paths. Never store a context in a struct
- Always derive a child context with a deadline before calling external services
- `errgroup.Group` for fan-out work that must short-circuit on first failure
- Mutex protects state, not just access. Document what each mutex guards in a comment
- `sync.Once` for lazy initialization. `sync/atomic` for single-word counters
- Channel close is a signal; never close from the receiver side

## Slices and Maps

- `make([]T, 0, capacity)` when the final size is known to avoid reallocations
- A nil slice and an empty slice behave identically for most operations except JSON encoding
- Maps are not safe for concurrent access. Use `sync.Map` only for caches with infrequent writes
- `for i := range slice` is often clearer than `for i, v := range slice` when `v` would be unused

## Interfaces

- Accept interfaces, return concrete types
- Define interfaces in the consumer's package, not the producer's
- Keep interfaces small. `io.Reader`, `io.Writer`, `error` are the model
- Avoid empty interface (`any`) in public APIs except where genuinely needed (encoding, reflection)

## Generics

- Use generics when the function body would otherwise duplicate logic across types
- Constraints first, type parameters second. Define meaningful constraint interfaces
- Don't reach for generics when interfaces or `any` are clearer

## Testing

- `testing.T` for unit tests, `testing.B` for benchmarks
- Table-driven tests with `t.Run(tc.name, ...)` for clear failure messages
- `t.Parallel()` for tests that don't share state
- `httptest.NewServer` over real HTTP listeners
- Fuzz testing with `func FuzzXxx(f *testing.F)` for parsers and decoders
- Avoid mocks; use real implementations behind interfaces

## Build Tags

- `//go:build integration` to gate integration tests behind `-tags integration`
- Platform-specific files via `_linux.go`, `_darwin.go` suffixes
- Never put significant logic behind build tags without testing every variant

## Module Hygiene

- Pin Go version in `go.mod`: `go 1.22`
- Run `go mod tidy` before every commit
- Vendor only when builds must be airgapped
- `go mod why <pkg>` to find why a transitive dependency is pulled in

## Performance

- Profile with `go test -bench=. -cpuprofile=cpu.out` then `go tool pprof`
- `sync.Pool` for short-lived heap allocations in hot paths
- Pre-allocate slices and maps when size is predictable
- `strings.Builder` for string concatenation in loops
- Beware of escape analysis: passing a pointer can move the value to the heap
