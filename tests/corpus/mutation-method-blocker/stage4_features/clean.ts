// Phase 35 fixture: idiomatic use of Stage 3 / Stage 4 features.
//
// Every block below uses the non-mutating form. The mutation-method-blocker
// hook must process this file and return zero hits.
//
// Coverage (10 positive idiomatic cases):
//   01. Array.fromAsync materializes an async iterable without push
//   02. AsyncIterator.map.toArray chain (Stage 3)
//   03. Iterator.range followed by toArray (Stage 2/3)
//   04. Iterator.from on a generator, drop and take helpers
//   05. Uint8Array.fromBase64 static factory (Stage 3)
//   06. Uint8Array.fromHex static factory (Stage 3)
//   07. Promise.try wrapping a synchronous throw
//   08. Promise.withResolvers as deferred construction
//   09. Error.isError duck-typed check (ES2024)
//   10. RegExp.escape returning a fresh string (ES2024)
//   11. Float16Array allocation (no mutation, ES2024)
//   12. Atomics.pause hint in busy loop (ES2024)
//   13. Pipeline operator (Stage 2 placeholder, parser-conditional)
//   14. Set.union for non-mutating composition (ES2024)
//   15. Map.groupBy returning a fresh Map (ES2024)

declare function fetchChunk(id: number): Promise<number>;

async function materialize(ids: readonly number[]): Promise<readonly number[]> {
  return Array.fromAsync(ids, (id) => fetchChunk(id));
}

async function mapAsync(): Promise<readonly number[]> {
  const asyncIter = (async function* () {
    yield 1;
    yield 2;
    yield 3;
  })();
  // ES2025 AsyncIterator helpers; assume runtime supports it.
  // @ts-expect-error - AsyncIterator helpers ship in TS 5.7+
  return (await asyncIter.map((x) => x * 2).toArray()) as readonly number[];
}

function rangeToArray(): readonly number[] {
  // @ts-expect-error - Iterator.range Stage 2/3
  return Iterator.range(0, 10).toArray();
}

function iteratorChain(): readonly number[] {
  function* nats() {
    let i = 0;
    while (true) yield i++;
  }
  // @ts-expect-error - Iterator helpers Stage 3
  return Iterator.from(nats()).drop(2).take(5).toArray();
}

function fromBase64(payload: string): Uint8Array {
  // @ts-expect-error - Stage 3 base64 static
  return Uint8Array.fromBase64(payload);
}

function fromHex(payload: string): Uint8Array {
  // @ts-expect-error - Stage 3 hex static
  return Uint8Array.fromHex(payload);
}

function tryCompute(): Promise<number> {
  return Promise.try(() => {
    const x = Math.random();
    if (x > 0.5) throw new Error("boom");
    return x;
  });
}

function deferred<T>(): { promise: Promise<T>; resolve: (v: T) => void; reject: (e: unknown) => void } {
  return Promise.withResolvers<T>();
}

function isErrorCheck(value: unknown): boolean {
  return Error.isError(value);
}

function safeRegex(input: string): RegExp {
  return new RegExp(RegExp.escape(input));
}

function allocFloat16(): Float16Array {
  return new Float16Array(16);
}

function busyWait(view: Int32Array): void {
  while (Atomics.load(view, 0) === 0) {
    Atomics.pause();
  }
}

function setUnion(a: ReadonlySet<number>, b: ReadonlySet<number>): ReadonlySet<number> {
  return a.union(b);
}

function groupOdd(items: readonly number[]): ReadonlyMap<string, readonly number[]> {
  return Map.groupBy(items, (n) => (n % 2 === 0 ? "even" : "odd"));
}

void [
  materialize,
  mapAsync,
  rangeToArray,
  iteratorChain,
  fromBase64,
  fromHex,
  tryCompute,
  deferred,
  isErrorCheck,
  safeRegex,
  allocFloat16,
  busyWait,
  setUnion,
  groupOdd,
];
