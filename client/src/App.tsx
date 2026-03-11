import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  LinearProgress,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import type {
  ComparisonOption,
  ComparisonScorecard,
  EvidenceItem,
  PublicResponseContract,
  QueryType,
} from "./contracts/public-contract";
import {
  clearStoredAuthSession,
  createSession,
  getSessionEvaluations,
  getSessionMessages,
  getStoredAuthSession,
  listSessions,
  login,
  persistAuthSession,
  sendMessage,
  type AuthSession,
  type ChatMessageRecord,
  type PersistedEvaluationRecord,
  type SessionSummary,
} from "./lib/backend";

const QUERY_TYPE_OPTIONS: Array<{ value: QueryType; label: string }> = [
  { value: "original_eval", label: "Original Evaluation" },
  { value: "acquisition_eval", label: "Acquisition Evaluation" },
  { value: "comparison", label: "Comparison" },
  { value: "followup_why_narrative", label: "Follow-up: Narrative" },
  { value: "followup_why_roi", label: "Follow-up: ROI" },
  { value: "followup_why_risk", label: "Follow-up: Risk" },
  { value: "followup_why_catalog", label: "Follow-up: Catalog Fit" },
  { value: "scenario_change_budget", label: "Scenario: Budget Change" },
  { value: "scenario_change_localization", label: "Scenario: Localization Change" },
  { value: "general_question", label: "General Question" },
];

function ProtectedRoute({
  isAuthenticated,
  children,
}: {
  isAuthenticated: boolean;
  children: JSX.Element;
}) {
  const location = useLocation();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}

function LoginPage({
  isAuthenticated,
  onLogin,
}: {
  isAuthenticated: boolean;
  onLogin: (username: string, password: string) => Promise<void>;
}) {
  const [username, setUsername] = useState("testuser");
  const [password, setPassword] = useState("testpass");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/app" replace />;
  }

  const submit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await onLogin(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        px: 3,
        background:
          "radial-gradient(circle at top, rgba(14,116,144,0.18), transparent 34%), linear-gradient(135deg, #f8f1df 0%, #efe2cc 45%, #d9e7e2 100%)",
      }}
    >
      <Card
        sx={{
          width: "min(100%, 460px)",
          borderRadius: 6,
          boxShadow: "0 28px 80px rgba(65, 53, 32, 0.18)",
          border: "1px solid rgba(54, 83, 72, 0.12)",
        }}
      >
        <CardContent sx={{ p: 4 }}>
          <Stack spacing={3}>
            <Box>
              <Typography variant="overline" color="text.secondary">
                StreamLogic Analyst Login
              </Typography>
              <Typography variant="h3" sx={{ mt: 1 }}>
                StreamLogic AI
              </Typography>
              <Typography color="text.secondary" sx={{ mt: 1.5 }}>
                Sign in to access protected sessions, chat history, scorecards, and evidence.
              </Typography>
            </Box>
            {error ? (
              <Alert severity="error" data-testid="auth-error">
                {error}
              </Alert>
            ) : null}
            <TextField
              label="Username"
              value={username}
              disabled={submitting}
              onChange={(event) => setUsername(event.target.value)}
              inputProps={{ "data-testid": "login-username" }}
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              disabled={submitting}
              onChange={(event) => setPassword(event.target.value)}
              inputProps={{ "data-testid": "login-password" }}
            />
            <Button
              size="large"
              variant="contained"
              data-testid="login-submit"
              disabled={submitting}
              onClick={submit}
            >
              {submitting ? "Signing in..." : "Sign In"}
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Card variant="outlined" sx={{ borderRadius: 4, minHeight: 120 }}>
      <CardContent>
        <Typography variant="overline" color="text.secondary">
          {label}
        </Typography>
        <Typography variant="h4" sx={{ mt: 1 }}>
          {value}
        </Typography>
      </CardContent>
    </Card>
  );
}

function EvidencePanel({ evidence }: { evidence: EvidenceItem[] }) {
  return (
    <Stack spacing={2} data-testid="evidence-panel">
      <Typography variant="h5">Evidence</Typography>
      {evidence.length === 0 ? (
        <Card variant="outlined" sx={{ borderRadius: 4 }}>
          <CardContent>
            <Typography color="text.secondary">No evidence was returned for this turn.</Typography>
          </CardContent>
        </Card>
      ) : null}
      {evidence.map((item) => (
        <Card key={item.evidence_id} variant="outlined" sx={{ borderRadius: 4 }}>
          <CardContent>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
              <Chip label={item.source_type} size="small" />
              <Chip label={item.retrieval_method} size="small" variant="outlined" />
              <Chip
                label={`Confidence ${Math.round(item.confidence_score * 100)}%`}
                size="small"
                color="primary"
                variant="outlined"
              />
            </Stack>
            <Typography sx={{ mb: 1.5 }}>{item.snippet}</Typography>
            <Typography variant="body2" color="text.secondary">
              {item.claim_it_supports}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.5 }}>
              {item.source_reference}
            </Typography>
          </CardContent>
        </Card>
      ))}
    </Stack>
  );
}

function ComparisonView({ comparison }: { comparison: ComparisonScorecard }) {
  return (
    <Stack spacing={2} data-testid="comparison-view">
      <Typography variant="h5">Comparison</Typography>
      <Typography color="text.secondary">{comparison.summary}</Typography>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        {comparison.options.map((option: ComparisonOption) => (
          <Card
            key={option.option_id}
            variant="outlined"
            sx={{
              flex: 1,
              borderRadius: 4,
              borderColor:
                comparison.winning_option_id === option.option_id ? "primary.main" : "divider",
            }}
          >
            <CardContent>
              <Stack spacing={1.5}>
                <Typography variant="h6">{option.label}</Typography>
                <Chip
                  label={option.recommendation ?? "Pending"}
                  color={comparison.winning_option_id === option.option_id ? "primary" : "default"}
                  sx={{ width: "fit-content" }}
                />
                <Typography variant="body2" color="text.secondary">
                  ROI {option.estimated_roi?.toFixed(2) ?? "n/a"}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Catalog fit {option.catalog_fit_score ?? "n/a"}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Risk {option.risk_level ?? "n/a"}
                </Typography>
              </Stack>
            </CardContent>
          </Card>
        ))}
      </Stack>
    </Stack>
  );
}

function ScorecardPanel({ response }: { response: PublicResponseContract }) {
  const { scorecard, meta } = response;

  return (
    <Stack spacing={2.5} data-testid="scorecard-panel">
      <Box>
        <Typography variant="h5">Scorecard</Typography>
        <Typography color="text.secondary">{scorecard.title}</Typography>
      </Box>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        <MetricCard label="Recommendation" value={scorecard.recommendation ?? "Pending"} />
        <MetricCard label="Estimated ROI" value={scorecard.estimated_roi?.toFixed(2) ?? "n/a"} />
        <MetricCard
          label="Catalog Fit"
          value={scorecard.catalog_fit_score?.toFixed(0) ?? "n/a"}
        />
      </Stack>
      <Card variant="outlined" sx={{ borderRadius: 4 }}>
        <CardContent>
          <Typography variant="overline" color="text.secondary">
            Analyst Confidence
          </Typography>
          <Typography variant="h6" sx={{ mt: 1 }}>
            {Math.round(meta.confidence * 100)}%
          </Typography>
          <LinearProgress
            variant="determinate"
            value={meta.confidence * 100}
            sx={{ mt: 1.5, height: 10, borderRadius: 999 }}
          />
          {meta.review_required ? (
            <Alert severity="warning" sx={{ mt: 2 }} data-testid="review-required">
              Manual review required before decision finalization.
            </Alert>
          ) : null}
          {meta.warnings.map((warning) => (
            <Alert key={warning} severity="warning" sx={{ mt: 2 }}>
              {warning}
            </Alert>
          ))}
        </CardContent>
      </Card>
      {scorecard.risk_flags.length > 0 ? (
        <Card variant="outlined" sx={{ borderRadius: 4 }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Risks
            </Typography>
            <Stack spacing={1.5}>
              {scorecard.risk_flags.map((flag) => (
                <Box key={flag.code}>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Chip label={flag.severity} size="small" />
                    <Typography variant="subtitle2">{flag.code}</Typography>
                  </Stack>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
                    {flag.summary}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </CardContent>
        </Card>
      ) : null}
      {scorecard.comparison ? <ComparisonView comparison={scorecard.comparison} /> : null}
    </Stack>
  );
}

function Workspace({ authSession, onLogout }: { authSession: AuthSession; onLogout: () => void }) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  const [messages, setMessages] = useState<ChatMessageRecord[]>([]);
  const [evaluations, setEvaluations] = useState<PersistedEvaluationRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [activeEvaluationId, setActiveEvaluationId] = useState<string | null>(null);

  const [messageInput, setMessageInput] = useState("");
  const [queryType, setQueryType] = useState<QueryType>("original_eval");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const activeResponse = useMemo(() => {
    if (evaluations.length === 0) {
      return null;
    }
    if (activeEvaluationId === null) {
      return evaluations[0].response;
    }
    const selected = evaluations.find((item) => item.id === activeEvaluationId);
    return selected?.response ?? evaluations[0].response;
  }, [activeEvaluationId, evaluations]);

  const refreshSessions = useCallback(async () => {
    setSessionsError(null);
    setSessionsLoading(true);
    try {
      const nextSessions = await listSessions();
      setSessions(nextSessions);
      setActiveSessionId((previous) => {
        if (previous && nextSessions.some((session) => session.id === previous)) {
          return previous;
        }
        return nextSessions[0]?.id ?? null;
      });
    } catch (err) {
      setSessionsError(err instanceof Error ? err.message : "Failed to load sessions");
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  const loadSessionHistory = useCallback(async (sessionId: string) => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const [messagesResponse, evaluationsResponse] = await Promise.all([
        getSessionMessages(sessionId),
        getSessionEvaluations(sessionId),
      ]);
      setMessages(messagesResponse.messages);
      setEvaluations(evaluationsResponse.evaluations);
      setActiveEvaluationId(evaluationsResponse.evaluations[0]?.id ?? null);
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : "Failed to load session history");
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      setEvaluations([]);
      setActiveEvaluationId(null);
      return;
    }
    void loadSessionHistory(activeSessionId);
  }, [activeSessionId, loadSessionHistory]);

  const handleCreateSession = async () => {
    setSessionsError(null);
    try {
      const created = await createSession();
      await refreshSessions();
      setActiveSessionId(created.session.id);
    } catch (err) {
      setSessionsError(err instanceof Error ? err.message : "Failed to create session");
    }
  };

  const handleSubmitMessage = async () => {
    const trimmed = messageInput.trim();
    if (!trimmed) {
      return;
    }

    setSubmitError(null);
    setSubmitting(true);
    try {
      let sessionId = activeSessionId;
      if (!sessionId) {
        const created = await createSession({ title: trimmed.slice(0, 64) });
        sessionId = created.session.id;
        setActiveSessionId(sessionId);
      }
      await sendMessage(sessionId, { message: trimmed, query_type: queryType });
      setMessageInput("");
      await refreshSessions();
      await loadSessionHistory(sessionId);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to send message");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: "100vh",
        background:
          "linear-gradient(180deg, rgba(250,248,241,0.96) 0%, rgba(233,241,238,0.98) 100%)",
        px: { xs: 2, md: 3 },
        py: { xs: 2, md: 3 },
      }}
    >
      <Stack spacing={3}>
        <Card
          sx={{
            borderRadius: 6,
            background:
              "linear-gradient(135deg, rgba(17,94,89,0.96) 0%, rgba(12,61,74,0.96) 100%)",
            color: "common.white",
          }}
        >
          <CardContent>
            <Stack
              direction={{ xs: "column", md: "row" }}
              spacing={2}
              justifyContent="space-between"
              alignItems={{ xs: "flex-start", md: "center" }}
            >
              <Box>
                <Typography variant="overline" sx={{ opacity: 0.8 }}>
                  Protected Workspace
                </Typography>
                <Typography variant="h3" sx={{ mt: 1 }}>
                  Authenticated Decision Support
                </Typography>
                <Typography sx={{ mt: 1.5, maxWidth: 760, opacity: 0.86 }}>
                  The frontend renders backend-validated `answer`, `scorecard`, `evidence`, and
                  minimal `meta` fields only.
                </Typography>
              </Box>
              <Stack direction="row" spacing={1.5} alignItems="center">
                <Chip
                  label={authSession.user.username}
                  sx={{ bgcolor: "rgba(255,255,255,0.12)", color: "common.white" }}
                />
                <Button variant="outlined" color="inherit" onClick={onLogout}>
                  Log Out
                </Button>
              </Stack>
            </Stack>
          </CardContent>
        </Card>

        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", lg: "280px minmax(0, 1fr) 380px" },
            gap: 2,
            alignItems: "start",
          }}
        >
          <Card variant="outlined" sx={{ borderRadius: 5 }}>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                <Typography variant="h6">Sessions</Typography>
                <Button size="small" onClick={handleCreateSession} data-testid="create-session">
                  New
                </Button>
              </Stack>
              {sessionsError ? <Alert severity="error">{sessionsError}</Alert> : null}
              {sessionsLoading ? <LinearProgress /> : null}
              <List disablePadding data-testid="session-list">
                {sessions.map((session) => (
                  <ListItemButton
                    key={session.id}
                    selected={session.id === activeSessionId}
                    onClick={() => setActiveSessionId(session.id)}
                    data-testid={`session-tab-${session.id}`}
                    sx={{ borderRadius: 3, mb: 1 }}
                  >
                    <ListItemText
                      primary={session.title ?? "Untitled Session"}
                      secondary={session.latest_query_type ?? "No evaluations yet"}
                    />
                  </ListItemButton>
                ))}
              </List>
              {!sessionsLoading && sessions.length === 0 ? (
                <Typography color="text.secondary" data-testid="empty-session-history">
                  No sessions yet. Create one or send a message to start.
                </Typography>
              ) : null}
            </CardContent>
          </Card>

          <Stack spacing={2}>
            <Card variant="outlined" sx={{ borderRadius: 5 }}>
              <CardContent>
                <Typography variant="h5" data-testid="chat-timeline">
                  Chat Timeline
                </Typography>
                <Typography color="text.secondary" sx={{ mt: 0.75, mb: 2 }}>
                  Session-backed conversation history
                </Typography>
                {historyError ? <Alert severity="error">{historyError}</Alert> : null}
                {historyLoading ? <LinearProgress sx={{ mb: 2 }} /> : null}
                <Stack spacing={2.5}>
                  {messages.map((message) => (
                    <Box
                      key={message.id}
                      sx={{
                        alignSelf: message.role === "user" ? "flex-end" : "flex-start",
                        maxWidth: "85%",
                      }}
                    >
                      <Card
                        sx={{
                          borderRadius: 4,
                          bgcolor: message.role === "user" ? "primary.main" : "background.paper",
                          color: message.role === "user" ? "primary.contrastText" : "text.primary",
                        }}
                      >
                        <CardContent>
                          <Typography variant="overline" sx={{ opacity: 0.7 }}>
                            {message.role}
                          </Typography>
                          <Typography sx={{ mt: 0.75 }}>{message.message_text}</Typography>
                        </CardContent>
                      </Card>
                    </Box>
                  ))}
                  {messages.length === 0 && !historyLoading ? (
                    <Typography color="text.secondary">No messages in this session yet.</Typography>
                  ) : null}
                </Stack>
                <Divider sx={{ my: 2.5 }} />
                {submitError ? <Alert severity="error">{submitError}</Alert> : null}
                <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
                  <TextField
                    select
                    label="Query Type"
                    value={queryType}
                    onChange={(event) => setQueryType(event.target.value as QueryType)}
                    sx={{ minWidth: { xs: "100%", md: 240 } }}
                    inputProps={{ "data-testid": "query-type" }}
                  >
                    {QUERY_TYPE_OPTIONS.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        {option.label}
                      </MenuItem>
                    ))}
                  </TextField>
                  <TextField
                    fullWidth
                    label="Ask a question"
                    value={messageInput}
                    disabled={submitting}
                    onChange={(event) => setMessageInput(event.target.value)}
                    inputProps={{ "data-testid": "chat-input" }}
                  />
                  <Button
                    variant="contained"
                    disabled={submitting}
                    onClick={handleSubmitMessage}
                    data-testid="chat-submit"
                  >
                    {submitting ? "Sending..." : "Send"}
                  </Button>
                </Stack>
              </CardContent>
            </Card>
          </Stack>

          <Stack spacing={2}>
            <Card variant="outlined" sx={{ borderRadius: 5 }}>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 1.5 }}>
                  Evaluations
                </Typography>
                <List disablePadding data-testid="evaluation-list">
                  {evaluations.map((evaluation) => (
                    <ListItemButton
                      key={evaluation.id}
                      selected={evaluation.id === activeEvaluationId}
                      onClick={() => setActiveEvaluationId(evaluation.id)}
                      sx={{ borderRadius: 3, mb: 1 }}
                    >
                      <ListItemText
                        primary={evaluation.response.scorecard.title}
                        secondary={evaluation.response.scorecard.query_type}
                      />
                    </ListItemButton>
                  ))}
                </List>
                {evaluations.length === 0 ? (
                  <Typography color="text.secondary">
                    No evaluations yet for the current session.
                  </Typography>
                ) : null}
              </CardContent>
            </Card>
            {activeResponse ? (
              <>
                <Card variant="outlined" sx={{ borderRadius: 5 }}>
                  <CardContent>
                    <Typography variant="h5" sx={{ mb: 1.5 }}>
                      Answer
                    </Typography>
                    <Typography data-testid="assistant-answer">{activeResponse.answer}</Typography>
                  </CardContent>
                </Card>
                <ScorecardPanel response={activeResponse} />
                <EvidencePanel evidence={activeResponse.evidence} />
              </>
            ) : (
              <Card variant="outlined" sx={{ borderRadius: 5 }}>
                <CardContent>
                  <Typography color="text.secondary" data-testid="empty-response">
                    No response available yet. Send a message to evaluate.
                  </Typography>
                </CardContent>
              </Card>
            )}
          </Stack>
        </Box>
      </Stack>
    </Box>
  );
}

function App() {
  const [authSession, setAuthSession] = useState<AuthSession | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setAuthSession(getStoredAuthSession());
    setHydrated(true);
  }, []);

  const handleLogin = async (username: string, password: string) => {
    const session = await login(username, password);
    persistAuthSession(session);
    setAuthSession(session);
  };

  const handleLogout = () => {
    clearStoredAuthSession();
    setAuthSession(null);
  };

  if (!hydrated) {
    return <LinearProgress />;
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={
          <LoginPage isAuthenticated={authSession !== null} onLogin={handleLogin} />
        }
      />
      <Route
        path="/app"
        element={
          <ProtectedRoute isAuthenticated={authSession !== null}>
            <Workspace authSession={authSession!} onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to={authSession !== null ? "/app" : "/login"} replace />} />
    </Routes>
  );
}

export default App;
