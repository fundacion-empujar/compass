import { isChunkLoadError } from "src/error/isChunkLoadError";

describe("isChunkLoadError", () => {
  test("returns true when the error name is ChunkLoadError", () => {
    // GIVEN an error whose name is ChunkLoadError (message unrelated)
    const error = new Error("anything");
    error.name = "ChunkLoadError";
    // THEN it is detected as a chunk-load error
    expect(isChunkLoadError(error)).toBe(true);
  });

  test("returns true when the message includes 'Loading chunk'", () => {
    // GIVEN a generic Error whose message is a webpack chunk-load failure
    // THEN it is detected as a chunk-load error
    expect(isChunkLoadError(new Error("Loading chunk 42 failed."))).toBe(true);
  });

  test("returns false for an unrelated Error", () => {
    expect(isChunkLoadError(new Error("some other failure"))).toBe(false);
  });

  test.each([[null], [undefined], ["Loading chunk 1 failed"], [{ name: "ChunkLoadError" }]])(
    "returns false for non-Error value %p",
    (value) => {
      // GIVEN a value that is not an Error instance (even if it looks chunk-like)
      // THEN it is not treated as a chunk-load error
      expect(isChunkLoadError(value)).toBe(false);
    }
  );
});
