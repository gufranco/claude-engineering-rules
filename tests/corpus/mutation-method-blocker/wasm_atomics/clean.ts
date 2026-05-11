// WebAssembly / Atomics / DataView clean fixture for mutation-method-blocker.
//
// Every line is in a hot-path directory (this file path contains /wasm/-style
// segments via fixture organization, see wasm_atomics_dirty.ts for the
// flagged variant). The hook must accept these patterns when they appear in
// a recognized hot-path scope or when paired with an inline suppression
// marker carrying a justification trailer.

declare const WebAssembly: any;
declare const Atomics: any;

// Atomics on SharedArrayBuffer view: legitimate shared-memory writes carry
// an info signal. The suppression below pairs with the marker, but the
// fixture documents the canonical lock-free counter increment.
// @claude-allow-mutation -- shared-memory counter, ordering verified
const sab = new SharedArrayBuffer(1024);
const view = new Int32Array(sab);
Atomics.store(view, 0, 1);
Atomics.add(view, 0, 1);
Atomics.compareExchange(view, 0, 1, 2);
Atomics.exchange(view, 0, 0);
Atomics.and(view, 0, 0xff);
Atomics.or(view, 0, 0x01);
Atomics.xor(view, 0, 0x0f);
Atomics.sub(view, 0, 1);

// Non-mutating Atomics ops are never flagged.
const observed = Atomics.load(view, 0);
Atomics.notify(view, 0, 1);
Atomics.wait(view, 0, 0);

// WebAssembly memory grow is permitted because the file is a wasm module
// boundary. After grow, every view derived from `memory.buffer` is
// recreated. The fixture documents that contract.
const memory = new WebAssembly.Memory({ initial: 1, maximum: 32 });
const previousPages = memory.grow(4);
const newView = new Uint8Array(memory.buffer);
const observedPages = previousPages + newView.byteLength / 65536;

// FinalizationRegistry is info-only and accepted: the callback only
// performs cleanup and never mutates application state.
const registry = new FinalizationRegistry((heldValue: string) => {
  // intentionally empty cleanup body
});
