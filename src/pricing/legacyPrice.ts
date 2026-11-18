import { execFile } from "node:child_process";
import path from "node:path";
import { Result, ok, err } from "../result";

export type Price = { net: string; vat: string; total: string };

const SCRIPT = path.join(__dirname, "..", "legacy", "price_calc.py");
const GENERIC_FAILURE = "Prisberäkningen kunde inte genomföras.";

export function resolveLegacyPython(
  env: NodeJS.ProcessEnv = process.env,
  platform: NodeJS.Platform = process.platform,
  projectRoot = path.resolve(__dirname, "..", ".."),
): string {
  if (env.LEGACY_PYTHON) return env.LEGACY_PYTHON;

  const platformPath = platform === "win32" ? path.win32 : path.posix;
  const executable = platform === "win32" ? ["Scripts", "python.exe"] : ["bin", "python"];
  return platformPath.join(projectRoot, ".venv", ...executable);
}

function isNotFoundResponse(value: unknown): boolean {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    Object.keys(value).length === 1 &&
    (value as { error?: unknown }).error === "finns inte"
  );
}

function isPrice(value: unknown): value is Price {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const price = value as Record<string, unknown>;
  return (
    Object.keys(price).length === 3 &&
    typeof price.net === "string" &&
    typeof price.vat === "string" &&
    typeof price.total === "string"
  );
}

// Brygga till den äldre prisberäkningen i Python. Allt pris räknas fortfarande där.
export function calcPrice(orderId: number): Promise<Result<Price>> {
  return new Promise((resolve, reject) => {
    try {
      execFile(
        resolveLegacyPython(),
        [SCRIPT, String(orderId)],
        { env: process.env },
        (error, stdout) => {
          let output: unknown;
          try {
            output = JSON.parse(stdout);
          } catch {
            reject(new Error(GENERIC_FAILURE));
            return;
          }

          if (error) {
            if (error.code === 1 && isNotFoundResponse(output)) {
              resolve(err("not_found", `Pris för beställning ${orderId} kunde inte räknas.`));
            } else {
              reject(new Error(GENERIC_FAILURE));
            }
            return;
          }

          if (!isPrice(output)) {
            reject(new Error(GENERIC_FAILURE));
            return;
          }
          resolve(ok(output));
        },
      );
    } catch {
      reject(new Error(GENERIC_FAILURE));
    }
  });
}
