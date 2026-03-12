import api, { AUTH_TOKEN_STORAGE_KEY } from "./api";
import type { PublicResponseContract, QueryType } from "../contracts/public-contract";
import { parsePublicResponseContract } from "../contracts/public-contract";

const AUTH_USER_STORAGE_KEY = "streamlogic-auth-user";

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  full_name: string | null;
}

export interface AuthSession {
  accessToken: string;
  user: AuthUser;
}

export interface SessionSummary {
  id: string;
  title: string | null;
  comparison_enabled: boolean;
  created_at: string;
  updated_at: string;
  message_count: number;
  latest_query_type: QueryType | null;
}

export interface SessionDetail {
  id: string;
  title: string | null;
  comparison_enabled: boolean;
  session_state: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface SessionCreateResponse {
  session: SessionDetail;
  reused_existing: boolean;
}

export type MessageRole = "user" | "assistant";

export interface ChatMessageRecord {
  id: string;
  session_id: string;
  role: MessageRole;
  message_text: string;
  query_type: QueryType | null;
  created_at: string;
}

export interface SessionMessagesResponse {
  session: SessionDetail;
  messages: ChatMessageRecord[];
}

export interface PersistedEvaluationRecord {
  id: string;
  session_id: string;
  message_id: string | null;
  query_type: QueryType;
  created_at: string;
  response: PublicResponseContract;
}

export interface SessionEvaluationsResponse {
  session: SessionDetail;
  evaluations: PersistedEvaluationRecord[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseAuthUser(value: unknown): AuthUser {
  if (!isRecord(value)) {
    throw new Error("Invalid user payload");
  }
  if (
    typeof value.id !== "number" ||
    typeof value.username !== "string" ||
    typeof value.email !== "string" ||
    (value.full_name !== null && typeof value.full_name !== "string")
  ) {
    throw new Error("Invalid user payload");
  }
  return value as unknown as AuthUser;
}

function parseSessionSummary(value: unknown): SessionSummary {
  if (!isRecord(value)) {
    throw new Error("Invalid session summary");
  }
  if (
    typeof value.id !== "string" ||
    (value.title !== null && typeof value.title !== "string") ||
    typeof value.comparison_enabled !== "boolean" ||
    typeof value.created_at !== "string" ||
    typeof value.updated_at !== "string" ||
    typeof value.message_count !== "number"
  ) {
    throw new Error("Invalid session summary");
  }
  return value as unknown as SessionSummary;
}

function parseSessionDetail(value: unknown): SessionDetail {
  if (!isRecord(value)) {
    throw new Error("Invalid session detail");
  }
  if (
    typeof value.id !== "string" ||
    (value.title !== null && typeof value.title !== "string") ||
    typeof value.comparison_enabled !== "boolean" ||
    typeof value.created_at !== "string" ||
    typeof value.updated_at !== "string"
  ) {
    throw new Error("Invalid session detail");
  }
  return value as unknown as SessionDetail;
}

function parseMessageRecord(value: unknown): ChatMessageRecord {
  if (!isRecord(value)) {
    throw new Error("Invalid chat message");
  }
  if (
    typeof value.id !== "string" ||
    typeof value.session_id !== "string" ||
    (value.role !== "user" && value.role !== "assistant") ||
    typeof value.message_text !== "string" ||
    typeof value.created_at !== "string"
  ) {
    throw new Error("Invalid chat message");
  }
  return value as unknown as ChatMessageRecord;
}

function parseEvaluationRecord(value: unknown): PersistedEvaluationRecord {
  if (!isRecord(value)) {
    throw new Error("Invalid evaluation record");
  }
  if (
    typeof value.id !== "string" ||
    typeof value.session_id !== "string" ||
    typeof value.query_type !== "string" ||
    typeof value.created_at !== "string"
  ) {
    throw new Error("Invalid evaluation record");
  }
  return {
    ...(value as unknown as PersistedEvaluationRecord),
    response: parsePublicResponseContract(value.response),
  };
}

export function getStoredAuthSession(): AuthSession | null {
  const token = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  const rawUser = localStorage.getItem(AUTH_USER_STORAGE_KEY);
  if (!token || !rawUser) {
    return null;
  }

  try {
    return {
      accessToken: token,
      user: parseAuthUser(JSON.parse(rawUser)),
    };
  } catch {
    clearStoredAuthSession();
    return null;
  }
}

export function persistAuthSession(session: AuthSession): void {
  localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, session.accessToken);
  localStorage.setItem(AUTH_USER_STORAGE_KEY, JSON.stringify(session.user));
}

export function clearStoredAuthSession(): void {
  localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  localStorage.removeItem(AUTH_USER_STORAGE_KEY);
}

export async function login(username: string, password: string): Promise<AuthSession> {
  const { data } = await api.post("/auth/login", { username, password });
  if (!isRecord(data) || typeof data.access_token !== "string") {
    throw new Error("Invalid login response");
  }
  return {
    accessToken: data.access_token,
    user: parseAuthUser(data.user),
  };
}

export async function listSessions(): Promise<SessionSummary[]> {
  const { data } = await api.get("/api/v1/sessions");
  if (!Array.isArray(data)) {
    throw new Error("Invalid sessions response");
  }
  return data.map(parseSessionSummary);
}

export async function createSession(
  payload?: { title?: string; comparison_enabled?: boolean; session_id?: string },
): Promise<SessionCreateResponse> {
  const { data } = await api.post("/api/v1/sessions", payload ?? {});
  if (!isRecord(data) || typeof data.reused_existing !== "boolean") {
    throw new Error("Invalid session create response");
  }
  return {
    session: parseSessionDetail(data.session),
    reused_existing: data.reused_existing,
  };
}

export async function getSessionMessages(sessionId: string): Promise<SessionMessagesResponse> {
  const { data } = await api.get(`/api/v1/sessions/${sessionId}/messages`);
  if (!isRecord(data) || !Array.isArray(data.messages)) {
    throw new Error("Invalid session messages response");
  }
  return {
    session: parseSessionDetail(data.session),
    messages: data.messages.map(parseMessageRecord),
  };
}

export async function getSessionEvaluations(
  sessionId: string,
): Promise<SessionEvaluationsResponse> {
  const { data } = await api.get(`/api/v1/sessions/${sessionId}/evaluations`);
  if (!isRecord(data) || !Array.isArray(data.evaluations)) {
    throw new Error("Invalid session evaluations response");
  }
  return {
    session: parseSessionDetail(data.session),
    evaluations: data.evaluations.map(parseEvaluationRecord),
  };
}

export async function sendMessage(
  sessionId: string,
  payload: { message: string; query_type?: QueryType; pitch_id?: string },
): Promise<PublicResponseContract> {
  const { data } = await api.post(`/api/v1/sessions/${sessionId}/messages`, payload);
  return parsePublicResponseContract(data);
}
