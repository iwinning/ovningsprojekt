import { ChildProcess, execFile } from "node:child_process";
import request from "supertest";
import { createApp } from "../src/app";
import { getOrder } from "../src/services/orderService";
import { resolveLegacyPython, calcPrice } from "../src/pricing/legacyPrice";

jest.mock("node:child_process", () => ({ execFile: jest.fn() }));
jest.mock("../src/services/orderService", () => ({
  createOrder: jest.fn(),
  cancelOrder: jest.fn(),
  getOrder: jest.fn(),
}));

const execFileMock = execFile as unknown as jest.Mock;
const getOrderMock = getOrder as jest.MockedFunction<typeof getOrder>;
const app = createApp();

type ExecFailure = (Error & { code?: string | number }) | null;

function mockExecFile(error: ExecFailure, stdout: string): void {
  execFileMock.mockImplementation(
    (
      _command: string,
      _args: string[],
      _options: object,
      callback: (error: ExecFailure, stdout: string, stderr: string) => void,
    ) => {
      callback(error, stdout, "");
      return {} as ChildProcess;
    },
  );
}

describe("resolveLegacyPython", () => {
  it("uses LEGACY_PYTHON when configured", () => {
    expect(resolveLegacyPython({ LEGACY_PYTHON: "custom-python" }, "win32", "C:\\project")).toBe(
      "custom-python",
    );
  });

  it.each([
    ["win32", "C:\\project\\.venv\\Scripts\\python.exe"],
    ["linux", "/project/.venv/bin/python"],
  ] as const)("uses the project virtualenv on %s", (platform, expected) => {
    const root = platform === "win32" ? "C:\\project" : "/project";
    expect(resolveLegacyPython({}, platform, root)).toBe(expected);
  });
});

describe("calcPrice", () => {
  beforeEach(() => {
    execFileMock.mockReset();
  });

  it("preserves the legacy price response shape", async () => {
    mockExecFile(null, '{"net":"950","vat":"237.5","total":"1187.5"}\n');

    await expect(calcPrice(1042)).resolves.toEqual({
      ok: true,
      value: { net: "950", vat: "237.5", total: "1187.5" },
    });
    expect(execFileMock.mock.calls[0][0]).toBe(resolveLegacyPython());
  });

  it("returns a sanitized HTTP 500 for an unexpected subprocess failure", async () => {
    getOrderMock.mockResolvedValue({
      ok: true,
      value: {
        id: 1042,
        customerId: 1,
        status: "new",
        discountCode: null,
        lines: [],
      },
    });
    mockExecFile(Object.assign(new Error("private spawn details"), { code: "ENOENT" }), "");

    const response = await request(app)
      .get("/orders/1042/price")
      .set("X-Customer-Id", "1")
      .timeout({ response: 1000 });

    expect(response.status).toBe(500);
    expect(response.body).toEqual({
      error: { code: "internal_error", message: "Ett internt fel inträffade." },
    });
  });

  it("returns a sanitized HTTP 500 when the order lookup fails", async () => {
    getOrderMock.mockRejectedValue(new Error("private database details"));

    const response = await request(app)
      .get("/orders/1042/price")
      .set("X-Customer-Id", "1")
      .timeout({ response: 1000 });

    expect(response.status).toBe(500);
    expect(response.body).toEqual({
      error: { code: "internal_error", message: "Ett internt fel inträffade." },
    });
  });

  it("maps only the expected CLI not-found response to not_found", async () => {
    mockExecFile(
      Object.assign(new Error("exit status 1"), { code: 1 }),
      '{"error":"finns inte"}\n',
    );

    await expect(calcPrice(9999)).resolves.toEqual({
      ok: false,
      error: {
        code: "not_found",
        message: "Pris för beställning 9999 kunde inte räknas.",
      },
    });
  });

  it.each([
    ["spawn failure", Object.assign(new Error("private spawn details"), { code: "ENOENT" }), ""],
    [
      "unexpected exit status",
      Object.assign(new Error("private process details"), { code: 2 }),
      '{"error":"finns inte"}',
    ],
    [
      "not-found payload with extra data",
      Object.assign(new Error("private process details"), { code: 1 }),
      '{"error":"finns inte","extra":true}',
    ],
    ["not-found payload on success", null, '{"error":"finns inte"}'],
    ["malformed output", null, "private malformed output"],
  ])("rejects safely for %s", async (_description, error, stdout) => {
    mockExecFile(error as ExecFailure, stdout);

    await expect(calcPrice(1042)).rejects.toThrow("Prisberäkningen kunde inte genomföras.");
  });

  it("sanitizes an exception thrown while starting the subprocess", async () => {
    execFileMock.mockImplementation(() => {
      throw new Error("private executable details");
    });

    await expect(calcPrice(1042)).rejects.toThrow("Prisberäkningen kunde inte genomföras.");
  });
});
