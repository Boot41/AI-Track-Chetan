import { MemoryRouter } from "react-router-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "../src/App";
import comparisonResponse from "../src/fixtures/phase0/comparison_response.json";
import followupResponse from "../src/fixtures/phase0/followup_response.json";
import standardResponse from "../src/fixtures/phase0/standard_evaluation_response.json";
import type { AuthSession } from "../src/lib/backend";
import * as backend from "../src/lib/backend";

vi.mock("../src/lib/backend", () => ({
  clearStoredAuthSession: vi.fn(),
  createSession: vi.fn(),
  getSessionEvaluations: vi.fn(),
  getSessionMessages: vi.fn(),
  getStoredAuthSession: vi.fn(),
  listSessions: vi.fn(),
  login: vi.fn(),
  persistAuthSession: vi.fn(),
  sendMessage: vi.fn(),
}));

function renderApp(initialPath = "/") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <App />
    </MemoryRouter>,
  );
}

const mockAuthSession: AuthSession = {
  accessToken: "token",
  user: {
    id: 1,
    username: "testuser",
    email: "test@example.com",
    full_name: "Test User",
  },
};

describe("App frontend integration flow", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(backend.getStoredAuthSession).mockReturnValue(null);
    vi.mocked(backend.listSessions).mockResolvedValue([]);
    vi.mocked(backend.getSessionMessages).mockResolvedValue({
      session: {
        id: "sess-1",
        title: "Neon Shore",
        comparison_enabled: false,
        session_state: null,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
      },
      messages: [],
    });
    vi.mocked(backend.getSessionEvaluations).mockResolvedValue({
      session: {
        id: "sess-1",
        title: "Neon Shore",
        comparison_enabled: false,
        session_state: null,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
      },
      evaluations: [],
    });
    vi.mocked(backend.createSession).mockResolvedValue({
      reused_existing: false,
      session: {
        id: "sess-1",
        title: "Neon Shore",
        comparison_enabled: false,
        session_state: null,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
      },
    });
  });

  it("redirects unauthenticated users to login", async () => {
    renderApp("/app");
    expect(await screen.findByTestId("login-submit")).toBeInTheDocument();
  });

  it("supports login and protected workspace navigation", async () => {
    vi.mocked(backend.login).mockResolvedValue(mockAuthSession);

    renderApp("/login");
    fireEvent.click(await screen.findByTestId("login-submit"));

    expect(await screen.findByTestId("create-session")).toBeInTheDocument();
    expect(backend.persistAuthSession).toHaveBeenCalledWith(mockAuthSession);
    expect(backend.listSessions).toHaveBeenCalled();
  });

  it("submits a chat message and renders answer, scorecard, and evidence", async () => {
    vi.mocked(backend.getStoredAuthSession).mockReturnValue(mockAuthSession);
    vi.mocked(backend.listSessions).mockResolvedValue([
      {
        id: "sess-1",
        title: "Neon Shore",
        comparison_enabled: false,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
        message_count: 0,
        latest_query_type: null,
      },
    ]);
    vi.mocked(backend.sendMessage).mockResolvedValue(standardResponse);
    vi.mocked(backend.getSessionMessages).mockResolvedValue({
      session: {
        id: "sess-1",
        title: "Neon Shore",
        comparison_enabled: false,
        session_state: null,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
      },
      messages: [
        {
          id: "m1",
          session_id: "sess-1",
          role: "user",
          message_text: "Should we greenlight Neon Shore?",
          query_type: "original_eval",
          created_at: "2026-01-01T00:00:00",
        },
        {
          id: "m2",
          session_id: "sess-1",
          role: "assistant",
          message_text: standardResponse.answer,
          query_type: "original_eval",
          created_at: "2026-01-01T00:00:01",
        },
      ],
    });
    vi.mocked(backend.getSessionEvaluations).mockResolvedValue({
      session: {
        id: "sess-1",
        title: "Neon Shore",
        comparison_enabled: false,
        session_state: null,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
      },
      evaluations: [
        {
          id: "e1",
          session_id: "sess-1",
          message_id: "m1",
          query_type: "original_eval",
          created_at: "2026-01-01T00:00:01",
          response: standardResponse,
        },
      ],
    });

    renderApp("/app");
    expect(await screen.findByText("StreamLogic AI")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "Should we greenlight Neon Shore?" },
    });
    fireEvent.click(screen.getByTestId("chat-submit"));

    expect(await screen.findByTestId("assistant-answer")).toHaveTextContent(
      "conditional greenlight",
    );
    expect(screen.getByTestId("scorecard-panel")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-panel")).toHaveTextContent("Neon Shore Pilot Script");
  });

  it("renders follow-up warnings and review-required meta", async () => {
    vi.mocked(backend.getStoredAuthSession).mockReturnValue(mockAuthSession);
    vi.mocked(backend.listSessions).mockResolvedValue([
      {
        id: "sess-1",
        title: "Follow-up",
        comparison_enabled: false,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
        message_count: 1,
        latest_query_type: "followup_why_roi",
      },
    ]);

    const followupWithReview = {
      ...followupResponse,
      meta: {
        ...followupResponse.meta,
        review_required: true,
      },
    };

    vi.mocked(backend.sendMessage).mockResolvedValue(followupWithReview);
    vi.mocked(backend.getSessionMessages).mockResolvedValue({
      session: {
        id: "sess-1",
        title: "Follow-up",
        comparison_enabled: false,
        session_state: null,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
      },
      messages: [
        {
          id: "m-follow-user",
          session_id: "sess-1",
          role: "user",
          message_text: "Why is ROI near breakeven?",
          query_type: "followup_why_roi",
          created_at: "2026-01-01T00:00:00",
        },
        {
          id: "m-follow-assistant",
          session_id: "sess-1",
          role: "assistant",
          message_text: followupWithReview.answer,
          query_type: "followup_why_roi",
          created_at: "2026-01-01T00:00:01",
        },
      ],
    });
    vi.mocked(backend.getSessionEvaluations).mockResolvedValue({
      session: {
        id: "sess-1",
        title: "Follow-up",
        comparison_enabled: false,
        session_state: null,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
      },
      evaluations: [
        {
          id: "e-follow",
          session_id: "sess-1",
          message_id: "m-follow",
          query_type: "followup_why_roi",
          created_at: "2026-01-01T00:00:01",
          response: followupWithReview,
        },
      ],
    });

    renderApp("/app");
    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "Why is ROI near breakeven?" },
    });
    fireEvent.click(screen.getByTestId("chat-submit"));

    expect(await screen.findByTestId("assistant-answer")).toHaveTextContent("breakeven");
    expect(screen.getByTestId("review-required")).toHaveTextContent("Manual review required");
    expect(screen.getByText("Follow-up answer is based on cached ROI outputs.")).toBeInTheDocument();
  });

  it("renders comparison responses when available", async () => {
    vi.mocked(backend.getStoredAuthSession).mockReturnValue(mockAuthSession);
    vi.mocked(backend.listSessions).mockResolvedValue([
      {
        id: "sess-2",
        title: "Comparison",
        comparison_enabled: true,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
        message_count: 1,
        latest_query_type: "comparison",
      },
    ]);
    vi.mocked(backend.sendMessage).mockResolvedValue(comparisonResponse);
    vi.mocked(backend.getSessionMessages).mockResolvedValue({
      session: {
        id: "sess-2",
        title: "Comparison",
        comparison_enabled: true,
        session_state: null,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
      },
      messages: [
        {
          id: "m2-user",
          session_id: "sess-2",
          role: "user",
          message_text: "Compare Neon Shore and Midnight Courts",
          query_type: "comparison",
          created_at: "2026-01-01T00:00:00",
        },
        {
          id: "m2-assistant",
          session_id: "sess-2",
          role: "assistant",
          message_text: comparisonResponse.answer,
          query_type: "comparison",
          created_at: "2026-01-01T00:00:01",
        },
      ],
    });
    vi.mocked(backend.getSessionEvaluations).mockResolvedValue({
      session: {
        id: "sess-2",
        title: "Comparison",
        comparison_enabled: true,
        session_state: null,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
      },
      evaluations: [
        {
          id: "e2",
          session_id: "sess-2",
          message_id: "m2",
          query_type: "comparison",
          created_at: "2026-01-01T00:00:01",
          response: comparisonResponse,
        },
      ],
    });

    renderApp("/app");
    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "Compare Neon Shore and Midnight Courts" },
    });
    fireEvent.click(screen.getByTestId("chat-submit"));
    expect(await screen.findByTestId("comparison-view")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("comparison-view")).toHaveTextContent("Midnight Courts");
    });
  });

  it("clears stale response content when a different session history fails to load", async () => {
    vi.mocked(backend.getStoredAuthSession).mockReturnValue(mockAuthSession);
    vi.mocked(backend.listSessions).mockResolvedValue([
      {
        id: "sess-1",
        title: "Session One",
        comparison_enabled: false,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
        message_count: 1,
        latest_query_type: "original_eval",
      },
      {
        id: "sess-2",
        title: "Session Two",
        comparison_enabled: false,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
        message_count: 0,
        latest_query_type: null,
      },
    ]);
    vi.mocked(backend.getSessionMessages).mockImplementation(async (sessionId: string) => {
      if (sessionId === "sess-1") {
        return {
          session: {
            id: "sess-1",
            title: "Session One",
            comparison_enabled: false,
            session_state: null,
            created_at: "2026-01-01T00:00:00",
            updated_at: "2026-01-01T00:00:00",
          },
          messages: [],
        };
      }
      throw new Error("Session unavailable");
    });
    vi.mocked(backend.getSessionEvaluations).mockImplementation(async (sessionId: string) => {
      if (sessionId === "sess-1") {
        return {
          session: {
            id: "sess-1",
            title: "Session One",
            comparison_enabled: false,
            session_state: null,
            created_at: "2026-01-01T00:00:00",
            updated_at: "2026-01-01T00:00:00",
          },
          evaluations: [
            {
              id: "e1",
              session_id: "sess-1",
              message_id: "m1",
              query_type: "original_eval",
              created_at: "2026-01-01T00:00:01",
              response: standardResponse,
            },
          ],
        };
      }
      throw new Error("Session unavailable");
    });

    vi.mocked(backend.sendMessage).mockResolvedValue(standardResponse);

    renderApp("/app");
    await waitFor(() => {
      expect(backend.getSessionEvaluations).toHaveBeenCalledWith("sess-1");
    });

    fireEvent.click(screen.getByTestId("session-tab-sess-2"));

    await waitFor(() => {
      expect(screen.queryByTestId("assistant-answer")).not.toBeInTheDocument();
    });
  });

  it("logs out on auth-expired event from a 401 session refresh", async () => {
    vi.mocked(backend.getStoredAuthSession).mockReturnValue(mockAuthSession);
    vi.mocked(backend.listSessions).mockImplementation(async () => {
      window.dispatchEvent(new Event("streamlogic-auth-expired"));
      throw new Error("Request failed with status code 401");
    });

    renderApp("/app");
    expect(await screen.findByTestId("login-submit")).toBeInTheDocument();
    expect(backend.clearStoredAuthSession).toHaveBeenCalled();
  });
});
