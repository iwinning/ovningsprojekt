import express, { ErrorRequestHandler } from "express";
import { customers } from "./routes/customers";
import { orders } from "./routes/orders";

export function createApp() {
  const app = express();
  app.use(express.json());
  app.get("/health", (_req, res) => {
    res.json({ status: "ok" });
  });
  app.use(customers);
  app.use(orders);
  const errorHandler: ErrorRequestHandler = (error, _req, res, next) => {
    if (res.headersSent) {
      next(error);
      return;
    }
    res.status(500).json({
      error: {
        code: "internal_error",
        message: "Ett internt fel inträffade.",
      },
    });
  };
  app.use(errorHandler);
  return app;
}
