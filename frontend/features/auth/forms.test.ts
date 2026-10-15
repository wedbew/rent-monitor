import { describe, expect, it } from "vitest";

import { ApiError, asProblem, TransportError } from "../../api/errors";
import {
  currentPasswordError,
  emailError,
  newPasswordError,
  readFailure,
  retryIn,
  weakPasswordMessage,
} from "./forms";

const problem = (over: Record<string, unknown>) => ({
  type: "urn:rentmonitor:problem:X",
  title: "t",
  status: 400,
  code: "VALIDATION_ERROR",
  instance: "/api/x",
  detail: null,
  errors: null,
  request_id: "req-1",
  ...over,
});

describe("validation", () => {
  it("accepts ordinary addresses and refuses the rest, in words", () => {
    expect(emailError("anna@example.com")).toBeNull();
    expect(emailError("  anna.k+tag@sub.example.co.uk ")).toBeNull();
    expect(emailError("")).toBe("Wpisz adres e-mail.");
    for (const bad of [
      "anna",
      "anna@",
      "@example.com",
      "anna@example",
      "a b@example.com",
      "anna@@example.com",
      `${"x".repeat(250)}@example.com`,
    ]) {
      expect(emailError(bad), bad).toMatch(/Wpisz poprawny adres/);
    }
  });

  it("counts characters, not bytes, for the password rules", () => {
    expect(newPasswordError("")).toBe("Wpisz hasło.");
    expect(newPasswordError("short")).toBe("Hasło musi mieć co najmniej 10 znaków.");
    expect(newPasswordError("zażółć gęślą")).toBeNull(); // 12 characters, more bytes
    expect(newPasswordError("żółć")).toMatch(/co najmniej 10/);
    expect(newPasswordError("x".repeat(129))).toBe("Hasło może mieć najwyżej 128 znaków.");
    expect(newPasswordError("x".repeat(128))).toBeNull();
    expect(currentPasswordError("")).toBe("Wpisz hasło.");
    expect(currentPasswordError("a")).toBeNull(); // sign-in never judges strength
  });
});

describe("weak password reasons", () => {
  it.each([
    ["too_short", /za krótkie/],
    ["too_long", /za długie/],
    ["common", /popularne/],
    ["contains_email", /adresu e-mail/],
    ["something-new", /zbyt słabe/],
    [undefined, /zbyt słabe/],
  ])("%s", (reason, expected) => {
    expect(weakPasswordMessage(reason)).toMatch(expected);
  });
});

describe("retryIn", () => {
  it.each([
    [1, "za 1\u00a0sekundę"],
    [2, "za 2\u00a0sekundy"],
    [5, "za 5\u00a0sekund"],
    [42, "za 42\u00a0sekundy"],
    [89, "za 89\u00a0sekund"],
    [90, "za 2\u00a0minuty"],
    [300, "za 5\u00a0minut"],
    [3600, "za 60\u00a0minut"],
  ])("%i s -> %s", (seconds, text) => {
    expect(retryIn(seconds)).toBe(text);
  });
});

describe("readFailure", () => {
  it("turns a transport failure into general copy", () => {
    expect(readFailure(new TransportError("network")).general?.action).toBe("retry");
    expect(readFailure(new TransportError("timeout")).code).toBeNull();
  });

  it("puts a weak password on the password field with the server's reason", () => {
    const out = readFailure(
      new ApiError(422, problem({ code: "WEAK_PASSWORD", reason: "contains_email" }) as never),
    );
    expect(out.fields["password"]).toMatch(/adresu e-mail/);
    expect(out.general).toBeNull();
    expect(out.code).toBe("WEAK_PASSWORD");
  });

  it("maps a 422 to the fields the server names, by the last element of `loc`", () => {
    const errors = [
      { loc: ["body", "email"], type: "string_pattern_mismatch", msg: "x" },
      { loc: ["body", "password"], type: "string_too_short", msg: "y" },
    ];
    const out = readFailure(new ApiError(422, problem({ errors }) as never));
    expect(Object.keys(out.fields).sort()).toEqual(["email", "password"]);
    expect(out.general).toBeNull();
  });

  it("describes any other problem with stable copy, the request id and the retry delay", () => {
    const out = readFailure(new ApiError(429, problem({ code: "RATE_LIMITED", status: 429 }) as never, 30));
    expect(out.general).toMatchObject({ requestId: "req-1", retryAfterS: 30, action: "waitAndRetry" });
    expect(out.fields).toEqual({});
  });

  it("does not trust an error that is not a problem", () => {
    expect(readFailure(new ApiError(502, null)).general?.action).toBe("reload");
    expect(readFailure(new Error("boom")).general?.action).toBe("reload");
  });
});

/**
 * Audit F11: a problem body is checked field by field before it is trusted. Each body below used to pass the
 * four-field check, and the first three made `readFailure` throw while an error was being shown.
 */
describe("a malformed problem body never breaks the form", () => {
  it.each([
    ["`errors` is not a list", { errors: "oops" }],
    ["an entry has no `loc` list", { errors: [{ loc: "body", msg: "x" }] }],
    ["`loc` holds an object", { errors: [{ loc: [{}], msg: "x" }] }],
    ["an entry has no message", { errors: [{ loc: ["body", "email"] }] }],
    ["`detail` is a number", { detail: 5 }],
    ["`request_id` is an object", { request_id: {} }],
  ])("%s: general 'unexpected response' copy, no exception", (_, over) => {
    const raw = problem(over);
    expect(asProblem(raw)).toBeNull();
    const out = readFailure(new ApiError(422, asProblem(raw)));
    expect(out.general?.action).toBe("reload");
    expect(out.fields).toEqual({});
  });

  it("accepts FastAPI's list indexes in `loc` and missing optional fields", () => {
    const raw = { ...problem({ errors: [{ loc: ["body", "items", 0], msg: "x", type: "t" }] }) };
    delete (raw as Record<string, unknown>)["detail"];
    delete (raw as Record<string, unknown>)["request_id"];
    const parsed = asProblem(raw);
    expect(parsed).not.toBeNull();
    expect(parsed?.detail).toBeNull();
    expect(readFailure(new ApiError(422, parsed)).fields).toEqual({ "0": "Sprawdź tę wartość." });
  });

  it("a weak-password reason never reaches the prototype", () => {
    for (const reason of ["toString", "__proto__", "constructor", "hasOwnProperty"])
      expect(weakPasswordMessage(reason)).toBe(
        "Hasło jest zbyt słabe. Wybierz dłuższe, mniej oczywiste hasło.",
      );
  });
});
