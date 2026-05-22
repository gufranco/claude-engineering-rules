// @allow-mutation -- corpus fixture; legacy mutation patterns intentionally retained for Phase 35 detector tests
//
// Phase 35 dirty fixture: legacy mutation patterns that the Stage 3/4
// features replace. The hook MUST flag each block when the file is not
// suppressed at the top. We mark the top-of-file marker so the fixture
// can ship in the repository without itself triggering the hook.
//
// Coverage (10 cases, each replaceable by a Stage 3/4 feature):
//   01. for await + push → Array.fromAsync
//   02. for await + push (renamed) → AsyncIterator.map.toArray
//   03. Array.from + push loop → Iterator.range
//   04. Manual range loop with push → Iterator.range
//   05. Uint8Array.prototype.setFromBase64 → Uint8Array.fromBase64
//   06. Uint8Array.prototype.setFromHex → Uint8Array.fromHex
//   07. Promise.resolve().then with state push → Promise.try
//   08. Manual Resolver closure → Promise.withResolvers
//   09. instanceof Error chain → Error.isError
//   10. Hand-rolled escape function pushing chars → RegExp.escape

declare function fetchChunk(id: number): Promise<number>;

async function legacyMaterialize(ids: readonly number[]): Promise<number[]> {
  const out: number[] = [];
  for await (const id of ids) {
    out.push(await fetchChunk(id));
  }
  return out;
}

async function legacyMapAsync(): Promise<number[]> {
  const asyncIter = (async function* () {
    yield 1;
    yield 2;
    yield 3;
  })();
  const result: number[] = [];
  for await (const x of asyncIter) {
    result.push(x * 2);
  }
  return result;
}

function legacyRangeFromArrayFrom(n: number): number[] {
  return Array.from({ length: n }, (_, i) => i);
}

function legacyManualRange(n: number): number[] {
  const xs: number[] = [];
  for (let i = 0; i < n; i++) {
    xs.push(i);
  }
  return xs;
}

function legacySetFromBase64(buf: Uint8Array, payload: string): void {
  buf.setFromBase64(payload);
}

function legacySetFromHex(buf: Uint8Array, payload: string): void {
  buf.setFromHex(payload);
}

function legacyResolveThenPush(state: string[]): Promise<void> {
  return Promise.resolve().then(() => {
    state.push("done");
  });
}

function legacyDeferred<T>(): { promise: Promise<T>; resolve: (v: T) => void } {
  let resolveFn!: (v: T) => void;
  const promise = new Promise<T>((res) => {
    resolveFn = res;
  });
  return { promise, resolve: resolveFn };
}

function legacyIsError(value: unknown): boolean {
  return value instanceof Error;
}

function legacyEscape(input: string): string {
  const out: string[] = [];
  for (const ch of input) {
    if (/[.*+?^${}()|[\]\\]/.test(ch)) {
      out.push("\\" + ch);
    } else {
      out.push(ch);
    }
  }
  return out.join("");
}

void [
  legacyMaterialize,
  legacyMapAsync,
  legacyRangeFromArrayFrom,
  legacyManualRange,
  legacySetFromBase64,
  legacySetFromHex,
  legacyResolveThenPush,
  legacyDeferred,
  legacyIsError,
  legacyEscape,
];
