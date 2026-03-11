import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function readFixture(name) {
  const fixturePath = path.resolve(__dirname, "../src/fixtures/phase0", name);
  const raw = await readFile(fixturePath, "utf-8");
  return JSON.parse(raw);
}

const standardResponse = await readFixture("standard_evaluation_response.json");
const followupResponse = await readFixture("followup_response.json");
const comparisonResponse = await readFixture("comparison_response.json");
const mockPort = Number(process.env.MOCK_BACKEND_PORT ?? "8011");

const state = {
  sessions: [],
  messagesBySession: new Map(),
  evaluationsBySession: new Map(),
  nextId: 1,
};

function json(res, statusCode, payload, extraHeaders = {}) {
  res.writeHead(statusCode, {
    "Content-Type": "application/json",
    ...extraHeaders,
  });
  res.end(JSON.stringify(payload));
}

function unauthorized(res) {
  json(res, 401, { detail: "Invalid token" });
}

function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk) => {
      body += String(chunk);
    });
    req.on("end", () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (err) {
        reject(err);
      }
    });
    req.on("error", reject);
  });
}

function nowIso() {
  return new Date().toISOString();
}

function requireAuth(req, res) {
  const auth = req.headers.authorization;
  if (auth !== "Bearer playwright-token") {
    unauthorized(res);
    return false;
  }
  return true;
}

function adaptResponseForQueryType(queryType) {
  if (queryType === "comparison") {
    return structuredClone(comparisonResponse);
  }
  if (queryType && queryType.startsWith("followup_")) {
    const payload = structuredClone(followupResponse);
    payload.scorecard.query_type = queryType;
    return payload;
  }
  const payload = structuredClone(standardResponse);
  if (queryType) {
    payload.scorecard.query_type = queryType;
  }
  return payload;
}

const server = createServer(async (req, res) => {
  if (!req.url || !req.method) {
    json(res, 404, { detail: "Not found" });
    return;
  }

  const requestUrl = new URL(req.url, `http://127.0.0.1:${mockPort}`);
  const pathname = requestUrl.pathname;

  if (req.method === "POST" && pathname === "/auth/login") {
    await parseBody(req);
    json(res, 200, {
      access_token: "playwright-token",
      token_type: "bearer",
      user: {
        id: 1,
        username: "testuser",
        email: "test@example.com",
        full_name: "Test User",
      },
    });
    return;
  }

  if (!pathname.startsWith("/api/v1/")) {
    json(res, 404, { detail: "Not found" });
    return;
  }

  if (!requireAuth(req, res)) {
    return;
  }

  if (req.method === "GET" && pathname === "/api/v1/sessions") {
    json(res, 200, state.sessions);
    return;
  }

  if (req.method === "POST" && pathname === "/api/v1/sessions") {
    const body = await parseBody(req);
    if (body.session_id) {
      const existing = state.sessions.find((session) => session.id === body.session_id);
      if (existing) {
        json(res, 200, {
          session: {
            id: existing.id,
            title: existing.title,
            comparison_enabled: existing.comparison_enabled,
            session_state: null,
            created_at: existing.created_at,
            updated_at: existing.updated_at,
          },
          reused_existing: true,
        });
        return;
      }
    }

    const id = `sess-${state.nextId++}`;
    const createdAt = nowIso();
    const session = {
      id,
      title: body.title ?? "Untitled Session",
      comparison_enabled: Boolean(body.comparison_enabled),
      created_at: createdAt,
      updated_at: createdAt,
      message_count: 0,
      latest_query_type: null,
    };
    state.sessions.unshift(session);
    state.messagesBySession.set(id, []);
    state.evaluationsBySession.set(id, []);
    json(res, 200, {
      session: {
        id,
        title: session.title,
        comparison_enabled: session.comparison_enabled,
        session_state: null,
        created_at: createdAt,
        updated_at: createdAt,
      },
      reused_existing: false,
    });
    return;
  }

  const sessionMessagesMatch = pathname.match(/^\/api\/v1\/sessions\/([^/]+)\/messages$/);
  if (sessionMessagesMatch) {
    const sessionId = sessionMessagesMatch[1];
    const session = state.sessions.find((item) => item.id === sessionId);
    if (!session) {
      json(res, 404, { detail: "Session not found" });
      return;
    }

    if (req.method === "GET") {
      const messages = state.messagesBySession.get(sessionId) ?? [];
      json(res, 200, {
        session: {
          id: session.id,
          title: session.title,
          comparison_enabled: session.comparison_enabled,
          session_state: null,
          created_at: session.created_at,
          updated_at: session.updated_at,
        },
        messages,
      });
      return;
    }

    if (req.method === "POST") {
      const body = await parseBody(req);
      const queryType = body.query_type ?? "original_eval";
      const responsePayload = adaptResponseForQueryType(queryType);
      const createdAt = nowIso();

      const messages = state.messagesBySession.get(sessionId) ?? [];
      const evaluations = state.evaluationsBySession.get(sessionId) ?? [];
      const userMessageId = `m-${state.nextId++}`;
      const assistantMessageId = `m-${state.nextId++}`;
      const evaluationId = `e-${state.nextId++}`;

      messages.push({
        id: userMessageId,
        session_id: sessionId,
        role: "user",
        message_text: body.message ?? "",
        query_type: queryType,
        created_at: createdAt,
      });
      messages.push({
        id: assistantMessageId,
        session_id: sessionId,
        role: "assistant",
        message_text: responsePayload.answer,
        query_type: responsePayload.scorecard.query_type,
        created_at: createdAt,
      });

      evaluations.unshift({
        id: evaluationId,
        session_id: sessionId,
        message_id: userMessageId,
        query_type: responsePayload.scorecard.query_type,
        created_at: createdAt,
        response: responsePayload,
      });

      state.messagesBySession.set(sessionId, messages);
      state.evaluationsBySession.set(sessionId, evaluations);
      session.message_count = messages.length;
      session.latest_query_type = responsePayload.scorecard.query_type;
      session.updated_at = createdAt;

      json(res, 200, responsePayload, { "X-Request-ID": `req-${state.nextId}` });
      return;
    }
  }

  const sessionEvaluationsMatch = pathname.match(/^\/api\/v1\/sessions\/([^/]+)\/evaluations$/);
  if (sessionEvaluationsMatch && req.method === "GET") {
    const sessionId = sessionEvaluationsMatch[1];
    const session = state.sessions.find((item) => item.id === sessionId);
    if (!session) {
      json(res, 404, { detail: "Session not found" });
      return;
    }
    const evaluations = state.evaluationsBySession.get(sessionId) ?? [];
    json(res, 200, {
      session: {
        id: session.id,
        title: session.title,
        comparison_enabled: session.comparison_enabled,
        session_state: null,
        created_at: session.created_at,
        updated_at: session.updated_at,
      },
      evaluations,
    });
    return;
  }

  json(res, 404, { detail: "Not found" });
});

server.listen(mockPort, () => {
  process.stdout.write(`mock backend listening on ${mockPort}\n`);
});
