import request from "supertest";
import { createApp } from "../src/app";
import { db } from "../src/db";
import { cancelOrder } from "../src/services/orderService";
import { closeDb, resetDb } from "./helpers/db";

const app = createApp();

beforeEach(resetDb);
afterAll(closeDb);

describe("POST /orders", () => {
  it("lägger en beställning med rader", async () => {
    const res = await request(app)
      .post("/orders")
      .set("X-Customer-Id", "3")
      .send({ lines: [{ product: "Musmatta", quantity: 2, unitPrice: 200 }] });
    expect(res.status).toBe(201);
    expect(res.body.customerId).toBe(3);
    expect(res.body.status).toBe("new");
    expect(res.body.lines).toEqual([{ product: "Musmatta", quantity: 2, unitPrice: "200.00" }]);
  });

  it("returnerar 400 utan rader", async () => {
    const res = await request(app).post("/orders").set("X-Customer-Id", "3").send({ lines: [] });
    expect(res.status).toBe(400);
  });

  it("returnerar 400 när antalet inte är positivt", async () => {
    const res = await request(app)
      .post("/orders")
      .set("X-Customer-Id", "3")
      .send({ lines: [{ product: "Musmatta", quantity: 0, unitPrice: 200 }] });
    expect(res.status).toBe(400);
  });

  it("returnerar 401 utan inloggning", async () => {
    const res = await request(app).post("/orders").send({ lines: [] });
    expect(res.status).toBe(401);
  });
});

describe("GET /orders/:id", () => {
  it("returnerar en egen beställning med rader", async () => {
    const res = await request(app).get("/orders/1042").set("X-Customer-Id", "1");
    expect(res.status).toBe(200);
    expect(res.body.lines).toHaveLength(2);
  });

  it("returnerar 403 för en annan kunds beställning", async () => {
    const res = await request(app).get("/orders/1042").set("X-Customer-Id", "2");
    expect(res.status).toBe(403);
    expect(res.body.error.code).toBe("forbidden");
  });

  it("returnerar 404 för en beställning som inte finns", async () => {
    const res = await request(app).get("/orders/9999").set("X-Customer-Id", "1");
    expect(res.status).toBe(404);
  });

  it("returnerar 400 för ett ogiltigt id", async () => {
    const res = await request(app).get("/orders/abc").set("X-Customer-Id", "1");
    expect(res.status).toBe(400);
  });
});

describe("GET /orders/:id/price", () => {
  it("räknar pris med moms via den äldre modulen", async () => {
    const res = await request(app).get("/orders/1042/price").set("X-Customer-Id", "1");
    expect(res.status).toBe(200);
    expect(Number(res.body.total)).toBe(1187.5);
  });
});

describe("POST /orders/:id/cancel", () => {
  it("returnerar ett generiskt 500 när databasen oväntat inte kan anslutas", async () => {
    const connectSpy = jest
      .spyOn(db, "connect")
      .mockImplementation(() => Promise.reject(new Error("sensitive database connection details")));

    try {
      const res = await request(app)
        .post("/orders/1043/cancel")
        .set("X-Customer-Id", "3");

      expect(res.status).toBe(500);
      expect(res.body).toEqual({
        error: {
          code: "internal_error",
          message: "Ett internt fel inträffade.",
        },
      });
      expect(JSON.stringify(res.body)).not.toContain("sensitive database connection details");
    } finally {
      connectSpy.mockRestore();
    }
  });

  it("avbryter en egen ny beställning inom tidsgränsen", async () => {
    await db.query("UPDATE orders SET created_at = clock_timestamp() WHERE id = $1", [1043]);

    const res = await request(app)
      .post("/orders/1043/cancel")
      .set("X-Customer-Id", "3");

    expect(res.status).toBe(200);
    expect(res.body).toEqual({ id: 1043, status: "cancelled" });
    const order = await db.query("SELECT status FROM orders WHERE id = $1", [1043]);
    expect(order.rows[0].status).toBe("cancelled");
  });

  it("returnerar 400 för ett ogiltigt id", async () => {
    const res = await request(app)
      .post("/orders/abc/cancel")
      .set("X-Customer-Id", "3");

    expect(res.status).toBe(400);
    expect(res.body.error.code).toBe("invalid_input");
  });

  it("returnerar 404 när beställningen saknas", async () => {
    const res = await request(app)
      .post("/orders/9999/cancel")
      .set("X-Customer-Id", "3");

    expect(res.status).toBe(404);
    expect(res.body.error.code).toBe("not_found");
  });

  it("returnerar 403 för en annan kunds beställning", async () => {
    const res = await request(app)
      .post("/orders/1043/cancel")
      .set("X-Customer-Id", "1");

    expect(res.status).toBe(403);
    expect(res.body.error.code).toBe("forbidden");
  });

  it("returnerar 401 utan inloggning", async () => {
    const res = await request(app).post("/orders/1043/cancel");

    expect(res.status).toBe(401);
  });

  it("returnerar 409 när statusen inte tillåter avbokning", async () => {
    const res = await request(app)
      .post("/orders/1042/cancel")
      .set("X-Customer-Id", "1");

    expect(res.status).toBe(409);
    expect(res.body.error.code).toBe("conflict");
  });

  it("returnerar 409 när beställningen är äldre än 30 minuter", async () => {
    await db.query(
      "UPDATE orders SET created_at = clock_timestamp() - interval '31 minutes' WHERE id = $1",
      [1043],
    );

    const res = await request(app)
      .post("/orders/1043/cancel")
      .set("X-Customer-Id", "3");

    expect(res.status).toBe(409);
    expect(res.body.error.code).toBe("conflict");
    const order = await db.query("SELECT status FROM orders WHERE id = $1", [1043]);
    expect(order.rows[0].status).toBe("new");
  });

  it("tillåter exakt 30 minuter och nekar en millisekund över gränsen", async () => {
    const now = new Date("2026-11-16T12:30:00.000Z");
    await db.query("UPDATE orders SET created_at = $1 WHERE id = $2", [
      new Date(now.getTime() - 30 * 60 * 1000),
      1043,
    ]);

    const atBoundary = await cancelOrder(1043, 3, now);
    expect(atBoundary).toEqual({ ok: true, value: { id: 1043, status: "cancelled" } });

    await resetDb();
    await db.query("UPDATE orders SET created_at = $1 WHERE id = $2", [
      new Date(now.getTime() - 30 * 60 * 1000 - 1),
      1043,
    ]);
    const pastBoundary = await cancelOrder(1043, 3, now);
    expect(pastBoundary).toEqual({
      ok: false,
      error: {
        code: "conflict",
        message: "Beställningen kan bara avbokas inom 30 minuter.",
      },
    });
  });

  it("nekar en beställning med framtida skapandetid", async () => {
    const now = new Date("2026-11-16T12:30:00.000Z");
    await db.query("UPDATE orders SET created_at = $1 WHERE id = $2", [
      new Date(now.getTime() + 1),
      1043,
    ]);

    const result = await cancelOrder(1043, 3, now);

    expect(result).toEqual({
      ok: false,
      error: {
        code: "conflict",
        message: "Beställningen kan bara avbokas inom 30 minuter.",
      },
    });
  });

  it("returnerar konflikt för en upprepad avbokning", async () => {
    await db.query("UPDATE orders SET created_at = clock_timestamp() WHERE id = $1", [1043]);
    await cancelOrder(1043, 3);

    const res = await request(app)
      .post("/orders/1043/cancel")
      .set("X-Customer-Id", "3");

    expect(res.status).toBe(409);
    expect(res.body.error.code).toBe("conflict");
  });

  it("serialiserar samtidiga avbokningar av samma beställning", async () => {
    await db.query("UPDATE orders SET created_at = clock_timestamp() WHERE id = $1", [1043]);
    const cancel = () =>
      request(app).post("/orders/1043/cancel").set("X-Customer-Id", "3");

    const responses = await Promise.all([cancel(), cancel()]);

    expect(responses.map((response) => response.status).sort()).toEqual([200, 409]);
    const order = await db.query("SELECT status FROM orders WHERE id = $1", [1043]);
    expect(order.rows[0].status).toBe("cancelled");
  });
});
