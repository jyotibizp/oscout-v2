import { newIds } from "./chime";

test("first load never chimes", () => {
  expect(newIds(null, [1, 2])).toEqual([]);
});

test("only newly appeared signal ids chime", () => {
  expect(newIds(new Set([1, 2]), [2, 3])).toEqual([3]);
  expect(newIds(new Set([1, 2]), [1])).toEqual([]);
});

test("rejected breakouts are tracked like signals: only new ids", () => {
  expect(newIds(new Set([7]), [8, 7])).toEqual([8]);
});
