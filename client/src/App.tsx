import { useEffect, useState } from "react";
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
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import type {
  ComparisonOption,
  ComparisonScorecard,
  EvidenceItem,
  PublicResponseContract,
} from "./contracts/public-contract";
import { fixtureConversations } from "./lib/fixtures";

const AUTH_STORAGE_KEY = "phase15-demo-auth";

interface AuthState {
  username: string;
}

interface TimelineMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
}

function loadAuthState(): AuthState | null {
  const raw = localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as AuthState;
  } catch {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

function saveAuthState(authState: AuthState | null): void {
  if (authState === null) {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    return;
  }

  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(authState));
}

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
  onLogin,
  isAuthenticated,
}: {
  onLogin: (username: string) => void;
  isAuthenticated: boolean;
}) {
  const navigate = useNavigate();
  const [username, setUsername] = useState("analyst@streamlogic.internal");
  const [password, setPassword] = useState("phase15-demo");

  if (isAuthenticated) {
    return <Navigate to="/app" replace />;
  }

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
                Phase 1.5 Fixture Shell
              </Typography>
              <Typography variant="h3" sx={{ mt: 1 }}>
                StreamLogic AI
              </Typography>
              <Typography color="text.secondary" sx={{ mt: 1.5 }}>
                Protected analyst workspace stub backed only by Phase 0 fixtures.
              </Typography>
            </Box>
            <TextField
              label="Work Email"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              inputProps={{ "data-testid": "login-username" }}
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              inputProps={{ "data-testid": "login-password" }}
            />
            <Button
              size="large"
              variant="contained"
              data-testid="login-submit"
              onClick={() => {
                onLogin(username);
                navigate("/app", { replace: true });
              }}
            >
              Enter Workspace
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
      <Typography variant="h5">Comparison Stub</Typography>
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
        <MetricCard
          label="Estimated ROI"
          value={scorecard.estimated_roi?.toFixed(2) ?? "n/a"}
        />
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

function Workspace({
  authState,
  onLogout,
}: {
  authState: AuthState;
  onLogout: () => void;
}) {
  const [activeConversationId, setActiveConversationId] = useState(fixtureConversations[0].id);
  const activeConversation =
    fixtureConversations.find((conversation) => conversation.id === activeConversationId) ??
    fixtureConversations[0];

  const timeline: TimelineMessage[] = [
    { id: `${activeConversation.id}-user`, role: "user", text: activeConversation.prompt },
    {
      id: `${activeConversation.id}-assistant`,
      role: "assistant",
      text: activeConversation.response.answer,
    },
  ];

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
                  Fixture-backed contract review
                </Typography>
                <Typography sx={{ mt: 1.5, maxWidth: 760, opacity: 0.86 }}>
                  The UI renders only the agreed public contract: answer, scorecard, evidence, and
                  minimal meta. No scoring, retrieval, or recommendation logic runs in the client.
                </Typography>
              </Box>
              <Stack direction="row" spacing={1.5} alignItems="center">
                <Chip
                  label={authState.username}
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
              <Typography variant="h6" sx={{ mb: 2 }}>
                Sessions
              </Typography>
              <List disablePadding>
                {fixtureConversations.map((conversation) => (
                  <ListItemButton
                    key={conversation.id}
                    selected={conversation.id === activeConversation.id}
                    onClick={() => setActiveConversationId(conversation.id)}
                    data-testid={`fixture-tab-${conversation.id}`}
                    sx={{ borderRadius: 3, mb: 1 }}
                  >
                    <ListItemText
                      primary={conversation.label}
                      secondary={conversation.response.scorecard.query_type}
                    />
                  </ListItemButton>
                ))}
              </List>
              <Divider sx={{ my: 2 }} />
              <Typography variant="body2" color="text.secondary" data-testid="route-guard-shell">
                Route guard is local-only in this phase. Real JWT-backed navigation remains a later
                phase.
              </Typography>
            </CardContent>
          </Card>

          <Stack spacing={2}>
            <Card variant="outlined" sx={{ borderRadius: 5 }}>
              <CardContent>
                <Typography variant="h5" data-testid="chat-timeline">
                  Chat Timeline
                </Typography>
                <Typography color="text.secondary" sx={{ mt: 0.75, mb: 2 }}>
                  Fixture conversation shell
                </Typography>
                <Stack spacing={2.5}>
                  {timeline.map((message) => (
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
                          <Typography sx={{ mt: 0.75 }}>{message.text}</Typography>
                        </CardContent>
                      </Card>
                    </Box>
                  ))}
                </Stack>
              </CardContent>
            </Card>
          </Stack>

          <Stack spacing={2}>
            <ScorecardPanel response={activeConversation.response} />
            <EvidencePanel evidence={activeConversation.response.evidence} />
          </Stack>
        </Box>
      </Stack>
    </Box>
  );
}

function App() {
  const [authState, setAuthState] = useState<AuthState | null>(null);

  useEffect(() => {
    setAuthState(loadAuthState());
  }, []);

  const handleLogin = (username: string) => {
    const nextState = { username };
    saveAuthState(nextState);
    setAuthState(nextState);
  };

  const handleLogout = () => {
    saveAuthState(null);
    setAuthState(null);
  };

  return (
    <Routes>
      <Route
        path="/login"
        element={<LoginPage onLogin={handleLogin} isAuthenticated={authState !== null} />}
      />
      <Route
        path="/app"
        element={
          <ProtectedRoute isAuthenticated={authState !== null}>
            <Workspace authState={authState ?? { username: "anonymous" }} onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />
      <Route
        path="*"
        element={<Navigate to={authState !== null ? "/app" : "/login"} replace />}
      />
    </Routes>
  );
}

export default App;
