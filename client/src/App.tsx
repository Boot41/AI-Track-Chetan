import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  IconButton,
  Grid,
} from "@mui/material";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import LogoutIcon from "@mui/icons-material/Logout";
import AddIcon from "@mui/icons-material/Add";
import InsightsIcon from "@mui/icons-material/Insights";
import ChatBubbleOutlineIcon from "@mui/icons-material/ChatBubbleOutline";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import PersonIcon from "@mui/icons-material/Person";

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
import { AUTH_EXPIRED_EVENT } from "./lib/api";

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
        background: "linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)",
      }}
    >
      <Card
        sx={{
          width: "min(100%, 420px)",
          borderRadius: 4,
          boxShadow: "0 10px 25px rgba(0,0,0,0.05)",
        }}
      >
        <CardContent sx={{ p: 4 }}>
          <Stack spacing={3}>
            <Box sx={{ textAlign: "center" }}>
              <Typography variant="h4" fontWeight="bold" gutterBottom>
                StreamLogic AI
              </Typography>
              <Typography color="text.secondary">
                Content Decision Support System
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
              sx={{ py: 1.5 }}
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
    <Box sx={{ flex: 1, p: 2, border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
      <Typography variant="caption" color="text.secondary" fontWeight="bold" sx={{ textTransform: "uppercase" }}>
        {label}
      </Typography>
      <Typography variant="h5" sx={{ mt: 0.5 }}>
        {value}
      </Typography>
    </Box>
  );
}

function EvidencePanel({ evidence }: { evidence: EvidenceItem[] }) {
  if (evidence.length === 0) return null;

  return (
    <Stack spacing={2} data-testid="evidence-panel">
      <Typography variant="subtitle1" fontWeight="bold">Supporting Evidence</Typography>
      {evidence.map((item) => (
        <Card key={item.evidence_id} variant="outlined" sx={{ borderRadius: 2, bgcolor: "grey.50" }}>
          <CardContent sx={{ p: 2, "&:last-child": { pb: 2 } }}>
            <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
              <Chip label={item.source_type} size="small" sx={{ height: 20, fontSize: "0.7rem" }} />
              <Chip label={`${Math.round(item.confidence_score * 100)}% Match`} size="small" color="primary" variant="outlined" sx={{ height: 20, fontSize: "0.7rem" }} />
            </Stack>
            <Typography variant="body2" sx={{ fontStyle: "italic", mb: 1 }}>
              "{item.snippet}"
            </Typography>
            <Typography variant="caption" color="text.secondary" display="block">
              Ref: {item.source_reference}
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
      <Typography variant="subtitle1" fontWeight="bold">Comparison Summary</Typography>
      <Typography variant="body2" color="text.secondary">{comparison.summary}</Typography>
      <Stack spacing={1.5}>
        {comparison.options.map((option: ComparisonOption) => (
          <Card
            key={option.option_id}
            variant="outlined"
            sx={{
              borderRadius: 2,
              borderColor: comparison.winning_option_id === option.option_id ? "primary.main" : "divider",
              borderWidth: comparison.winning_option_id === option.option_id ? 2 : 1,
            }}
          >
            <CardContent sx={{ p: 2, "&:last-child": { pb: 2 } }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="subtitle2" fontWeight="bold">{option.label}</Typography>
                <Chip
                  label={option.recommendation ?? "Pending"}
                  size="small"
                  color={comparison.winning_option_id === option.option_id ? "primary" : "default"}
                />
              </Stack>
              <Grid container spacing={1} sx={{ mt: 1 }}>
                <Grid item xs={4}>
                  <Typography variant="caption" color="text.secondary">ROI: {option.estimated_roi?.toFixed(2) ?? "n/a"}</Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant="caption" color="text.secondary">Fit: {option.catalog_fit_score ?? "n/a"}</Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant="caption" color="text.secondary">Risk: {option.risk_level ?? "n/a"}</Typography>
                </Grid>
              </Grid>
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
    <Stack spacing={3} data-testid="scorecard-panel">
      <Box>
        <Typography variant="h6" fontWeight="bold">{scorecard.title}</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ textTransform: "uppercase" }}>
          {scorecard.query_type.replace(/_/g, " ")}
        </Typography>
      </Box>

      <Stack direction="row" spacing={2}>
        <MetricCard label="Recommendation" value={scorecard.recommendation ?? "Pending"} />
        <MetricCard label="Est. ROI" value={scorecard.estimated_roi?.toFixed(2) ?? "n/a"} />
      </Stack>

      <Box>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="subtitle2">System Confidence</Typography>
          <Typography variant="subtitle2" fontWeight="bold">{Math.round(meta.confidence * 100)}%</Typography>
        </Stack>
        <LinearProgress
          variant="determinate"
          value={meta.confidence * 100}
          sx={{ height: 6, borderRadius: 3 }}
        />
        {meta.review_required && (
          <Alert severity="warning" sx={{ mt: 2, py: 0 }} icon={false} data-testid="review-required">
            <Typography variant="caption">Manual review required.</Typography>
          </Alert>
        )}
        {meta.warnings.map((warning) => (
          <Alert key={warning} severity="warning" sx={{ mt: 1, py: 0 }} icon={false}>
            <Typography variant="caption">{warning}</Typography>
          </Alert>
        ))}
      </Box>

      {scorecard.risk_flags.length > 0 && (
        <Box>
          <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1 }}>Risk Flags</Typography>
          <Stack spacing={1}>
            {scorecard.risk_flags.map((flag) => (
              <Stack key={flag.code} direction="row" spacing={1} alignItems="center">
                <Chip label={flag.severity} size="small" color={flag.severity === "HIGH" || flag.severity === "BLOCKER" ? "error" : "warning"} sx={{ height: 18, fontSize: "0.65rem" }} />
                <Typography variant="body2">{flag.summary}</Typography>
              </Stack>
            ))}
          </Stack>
        </Box>
      )}

      {scorecard.comparison && <ComparisonView comparison={scorecard.comparison} />}
    </Stack>
  );
}

function Workspace({ authSession, onLogout }: { authSession: AuthSession; onLogout: () => void }) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  const [messages, setMessages] = useState<ChatMessageRecord[]>([]);
  const [evaluations, setEvaluations] = useState<PersistedEvaluationRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [activeEvaluationId, setActiveEvaluationId] = useState<string | null>(null);

  const [messageInput, setMessageInput] = useState("");
  const [queryType, setQueryType] = useState<QueryType>("original_eval");
  const [submitting, setSubmitting] = useState(false);
  const historyRequestRef = useRef(0);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const activeResponse = useMemo(() => {
    if (evaluations.length === 0) return null;
    const selected = activeEvaluationId 
      ? evaluations.find((item) => item.id === activeEvaluationId)
      : evaluations[0];
    return selected?.response ?? evaluations[0].response;
  }, [activeEvaluationId, evaluations]);

  const refreshSessions = useCallback(async () => {
    try {
      const nextSessions = await listSessions();
      setSessions(nextSessions);
      if (!activeSessionId && nextSessions.length > 0) {
        setActiveSessionId(nextSessions[0].id);
      }
    } catch (err) {
      console.error("Failed to load sessions", err);
    }
  }, [activeSessionId]);

  const loadSessionHistory = useCallback(async (sessionId: string) => {
    const requestId = ++historyRequestRef.current;
    setHistoryLoading(true);
    try {
      const [messagesResponse, evaluationsResponse] = await Promise.all([
        getSessionMessages(sessionId),
        getSessionEvaluations(sessionId),
      ]);
      if (requestId !== historyRequestRef.current) return;
      setMessages(messagesResponse.messages);
      setEvaluations(evaluationsResponse.evaluations);
      setActiveEvaluationId(evaluationsResponse.evaluations[0]?.id ?? null);
    } catch (err) {
      console.error("Failed to load history", err);
    } finally {
      if (requestId === historyRequestRef.current) setHistoryLoading(false);
    }
  }, []);

  useEffect(() => { void refreshSessions(); }, [refreshSessions]);

  useEffect(() => {
    if (activeSessionId) void loadSessionHistory(activeSessionId);
  }, [activeSessionId, loadSessionHistory]);

  useEffect(() => {
    if (typeof chatEndRef.current?.scrollIntoView === "function") {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const handleCreateSession = async () => {
    try {
      const created = await createSession();
      const summary: SessionSummary = {
        id: created.session.id,
        title: created.session.title,
        comparison_enabled: created.session.comparison_enabled,
        created_at: created.session.created_at,
        updated_at: created.session.updated_at,
        message_count: 0,
        latest_query_type: null,
      };
      setSessions((prev) => [summary, ...prev]);
      setActiveSessionId(created.session.id);
    } catch (err) {
      console.error("Failed to create session", err);
    }
  };

  const handleSubmitMessage = async () => {
    const trimmed = messageInput.trim();
    if (!trimmed || submitting) return;

    setSubmitting(true);
    try {
      let sessionId = activeSessionId;
      if (!sessionId) {
        const created = await createSession({ title: trimmed.slice(0, 32) });
        sessionId = created.session.id;
        setActiveSessionId(sessionId);
      }
      await sendMessage(sessionId, { message: trimmed, query_type: queryType });
      setMessageInput("");
      await loadSessionHistory(sessionId);
      void refreshSessions();
    } catch (err) {
      console.error("Failed to send message", err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100vh", bgcolor: "background.default" }}>
      {/* Header */}
      <Box sx={{ 
        height: 64, 
        display: "flex", 
        alignItems: "center", 
        justifyContent: "space-between", 
        px: 3, 
        borderBottom: "1px solid", 
        borderColor: "divider",
        bgcolor: "background.paper",
        zIndex: 1100
      }}>
        <Typography variant="h6" fontWeight="bold" color="primary">StreamLogic AI</Typography>
        <Stack direction="row" spacing={2} alignItems="center">
          <Typography variant="body2" color="text.secondary">{authSession.user.username}</Typography>
          <IconButton size="small" onClick={onLogout}><LogoutIcon fontSize="small" /></IconButton>
        </Stack>
      </Box>

      <Box sx={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Sidebar */}
        <Box sx={{ width: 280, borderRight: "1px solid", borderColor: "divider", display: "flex", flexDirection: "column", bgcolor: "grey.50" }}>
          <Box sx={{ p: 2 }}>
            <Button 
              fullWidth 
              variant="outlined" 
              startIcon={<AddIcon />} 
              onClick={handleCreateSession}
              sx={{ borderRadius: 2, textTransform: "none" }}
              data-testid="create-session"
            >
              New Session
            </Button>
          </Box>
          <Box sx={{ flex: 1, overflowY: "auto" }}>
            <List sx={{ px: 1 }} data-testid="session-list">
              {sessions.map((session) => (
                <ListItemButton
                  key={session.id}
                  selected={session.id === activeSessionId}
                  onClick={() => setActiveSessionId(session.id)}
                  sx={{ borderRadius: 2, mb: 0.5 }}
                  data-testid={`session-tab-${session.id}`}
                >
                  <ListItemText
                    primary={session.title ?? "Untitled Session"}
                    primaryTypographyProps={{ variant: "body2", fontWeight: session.id === activeSessionId ? "bold" : "medium", noWrap: true }}
                    secondary={session.latest_query_type?.replace(/_/g, " ") ?? "No activity"}
                    secondaryTypographyProps={{ variant: "caption", noWrap: true }}
                  />
                </ListItemButton>
              ))}
            </List>
          </Box>
        </Box>

        {/* Chat Area */}
        <Box sx={{ flex: 1, display: "flex", flexDirection: "column", position: "relative" }}>
          <Box sx={{ flex: 1, overflowY: "auto", p: 3, display: "flex", flexDirection: "column" }}>
            <Stack spacing={3}>
              {messages.map((msg) => (
                <Box key={msg.id} sx={{ 
                  display: "flex", 
                  flexDirection: "column",
                  alignItems: msg.role === "user" ? "flex-end" : "start",
                  maxWidth: "90%",
                  alignSelf: msg.role === "user" ? "flex-end" : "start"
                }}>
                  <Stack direction="row" spacing={1} alignItems="flex-start">
                    {msg.role === "assistant" && <SmartToyIcon color="primary" sx={{ mt: 1, fontSize: 20 }} />}
                    <Box sx={{ 
                      p: 2, 
                      borderRadius: 3, 
                      bgcolor: msg.role === "user" ? "primary.main" : "background.paper",
                      color: msg.role === "user" ? "primary.contrastText" : "text.primary",
                      boxShadow: msg.role === "user" ? "none" : "0 2px 8px rgba(0,0,0,0.05)",
                      border: msg.role === "user" ? "none" : "1px solid",
                      borderColor: "divider"
                    }}>
                      <Typography variant="body2" data-testid={msg.role === "assistant" ? "assistant-answer" : undefined}>
                        {msg.message_text}
                      </Typography>
                    </Box>
                    {msg.role === "user" && <PersonIcon color="action" sx={{ mt: 1, fontSize: 20 }} />}
                  </Stack>
                </Box>
              ))}
              <div ref={chatEndRef} />
            </Stack>
            {messages.length === 0 && !historyLoading && (
              <Box sx={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", opacity: 0.5 }}>
                <Stack alignItems="center" spacing={1}>
                  <ChatBubbleOutlineIcon sx={{ fontSize: 48 }} />
                  <Typography>Start a new analysis by asking a question.</Typography>
                </Stack>
              </Box>
            )}
          </Box>

          <Box sx={{ p: 3, borderTop: "1px solid", borderColor: "divider", bgcolor: "background.paper" }}>
            <Stack direction="row" spacing={2}>
              <TextField
                select
                size="small"
                value={queryType}
                onChange={(e) => setQueryType(e.target.value as QueryType)}
                sx={{ width: 200 }}
                inputProps={{ "data-testid": "query-type" }}
              >
                {QUERY_TYPE_OPTIONS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                ))}
              </TextField>
              <TextField
                fullWidth
                size="small"
                placeholder="Ask about a project, risk, or ROI..."
                value={messageInput}
                disabled={submitting}
                onChange={(e) => setMessageInput(e.target.value)}
                onKeyPress={(e) => e.key === "Enter" && handleSubmitMessage()}
                inputProps={{ "data-testid": "chat-input" }}
              />
              <Button 
                variant="contained" 
                disabled={submitting} 
                onClick={handleSubmitMessage}
                sx={{ px: 4 }}
                data-testid="chat-submit"
              >
                {submitting ? "..." : "Send"}
              </Button>
            </Stack>
          </Box>
        </Box>

        {/* Analysis Panel */}
        <Box sx={{ width: 400, borderLeft: "1px solid", borderColor: "divider", display: "flex", flexDirection: "column", bgcolor: "background.paper" }}>
          <Box sx={{ p: 2, borderBottom: "1px solid", borderColor: "divider", display: "flex", alignItems: "center", gap: 1 }}>
            <InsightsIcon color="primary" />
            <Typography variant="subtitle1" fontWeight="bold">Insights & Analysis</Typography>
          </Box>
          <Box sx={{ flex: 1, overflowY: "auto", p: 3 }}>
            {activeResponse ? (
              <Stack spacing={4}>
                <ScorecardPanel response={activeResponse} />
                <Divider />
                <EvidencePanel evidence={activeResponse.evidence} />
              </Stack>
            ) : (
              <Box sx={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", textAlign: "center", px: 4 }} data-testid="empty-response">
                <Typography color="text.secondary" variant="body2">
                  Send a message to view detailed scorecard and evidence analysis.
                </Typography>
              </Box>
            )}
          </Box>
        </Box>
      </Box>
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

  const handleLogout = useCallback(() => {
    clearStoredAuthSession();
    setAuthSession(null);
  }, []);

  useEffect(() => {
    const onAuthExpired = () => handleLogout();
    window.addEventListener(AUTH_EXPIRED_EVENT, onAuthExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onAuthExpired);
  }, [handleLogout]);

  if (!hydrated) return <LinearProgress />;

  return (
    <Routes>
      <Route path="/login" element={<LoginPage isAuthenticated={authSession !== null} onLogin={handleLogin} />} />
      <Route path="/app" element={
        <ProtectedRoute isAuthenticated={authSession !== null}>
          <Workspace authSession={authSession!} onLogout={handleLogout} />
        </ProtectedRoute>
      } />
      <Route path="*" element={<Navigate to={authSession !== null ? "/app" : "/login"} replace />} />
    </Routes>
  );
}

export default App;
