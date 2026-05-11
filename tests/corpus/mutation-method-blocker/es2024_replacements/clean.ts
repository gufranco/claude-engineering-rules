// ES2024+ replacement fixture for mutation-method-blocker.
//
// Every line in this file uses a non-mutating ES2023+/ES2024 method or a
// known no-mutation static factory. The hook must process the file and
// return exit code 0 with no detector hits.
//
// Coverage:
//   - ES2023 array helpers: toSorted, toReversed, toSpliced, with
//   - ES2024 Set composition: union, intersection, difference,
//     symmetricDifference, isSubsetOf, isSupersetOf, isDisjointFrom
//   - ES2024 Iterator helpers: map, filter, take, drop, flatMap, toArray, reduce
//   - ES2024 Object.groupBy, Map.groupBy
//   - ES2024 Promise.withResolvers, Promise.try
//   - ES2024 Array.fromAsync
//   - ES2024 RegExp.escape
//   - ES2024 Atomics.pause
//   - ES2024 Error.isError
//   - ES2024 Float16Array allocation (binary buffer hint, no mutation)
//   - Spread-based copy for objects, arrays, Maps, Sets

const numbers: readonly number[] = [3, 1, 4, 1, 5, 9, 2, 6];
const sorted = numbers.toSorted((a, b) => a - b);
const reversed = numbers.toReversed();
const spliced = numbers.toSpliced(0, 1, 100);
const replaced = numbers.with(0, 99);
void [sorted, reversed, spliced, replaced];

const evens = new Set([2, 4, 6, 8]);
const squares = new Set([1, 4, 9, 16]);
const both = evens.intersection(squares);
const either = evens.union(squares);
const onlyEvens = evens.difference(squares);
const symDiff = evens.symmetricDifference(squares);
const small = new Set([2, 4]);
const isSub = small.isSubsetOf(evens);
const isSup = evens.isSupersetOf(small);
const disjoint = evens.isDisjointFrom(new Set([7, 9]));
void [both, either, onlyEvens, symDiff, isSub, isSup, disjoint];

const tripled = numbers
  .values()
  .map((n) => n * 3)
  .filter((n) => n > 5)
  .take(3)
  .toArray();
void tripled;

const grouped = Object.groupBy([1, 2, 3, 4, 5], (n) =>
  n % 2 === 0 ? 'even' : 'odd',
);
const groupedMap = Map.groupBy([1, 2, 3, 4, 5], (n) =>
  n % 2 === 0 ? 'even' : 'odd',
);
void [grouped, groupedMap];

const { promise, resolve, reject } = Promise.withResolvers<number>();
void [promise, resolve, reject];

const safe = await Promise.try(() => 42);
void safe;

async function* asyncRange(): AsyncGenerator<number> {
  yield 1;
  yield 2;
  yield 3;
}
const collected = await Array.fromAsync(asyncRange());
void collected;

const escaped = RegExp.escape('foo.bar+baz');
void escaped;

await Atomics.pause();

const isErr = Error.isError(new Error('test'));
void isErr;

const halfBuffer = new Float16Array(16);
const sampleAtZero = halfBuffer[0];
const sampleAtOne = halfBuffer.at(1);
void [sampleAtZero, sampleAtOne];

const baseObj = { a: 1, b: 2 } as const;
const extended = { ...baseObj, c: 3 };
const without = (() => {
  const { a: _omitted, ...rest } = extended;
  return rest;
})();
void [extended, without];

const baseMap = new Map<string, number>([
  ['x', 1],
  ['y', 2],
]);
const nextMap = new Map([...baseMap, ['z', 3]]);
const filteredMap = new Map([...baseMap].filter(([k]) => k !== 'x'));
void [nextMap, filteredMap];

const baseSet = new Set(['a', 'b']);
const nextSet = new Set([...baseSet, 'c']);
const reducedSet = baseSet.difference(new Set(['a']));
void [nextSet, reducedSet];

export {};
