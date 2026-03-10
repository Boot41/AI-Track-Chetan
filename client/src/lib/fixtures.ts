import comparisonResponse from "../fixtures/phase0/comparison_response.json";
import followupResponse from "../fixtures/phase0/followup_response.json";
import standardResponse from "../fixtures/phase0/standard_evaluation_response.json";
import type { PublicResponseContract } from "../contracts/public-contract";

export interface FixtureConversation {
  id: string;
  label: string;
  prompt: string;
  response: PublicResponseContract;
}

export const fixtureConversations: FixtureConversation[] = [
  {
    id: "standard",
    label: "Original Evaluation",
    prompt: "Should we greenlight Neon Shore as a new original series?",
    response: standardResponse as PublicResponseContract,
  },
  {
    id: "followup",
    label: "ROI Follow-Up",
    prompt: "Why did the ROI stay close to breakeven for Neon Shore?",
    response: followupResponse as PublicResponseContract,
  },
  {
    id: "comparison",
    label: "Comparison",
    prompt: "Compare Neon Shore against Midnight Courts before we allocate budget.",
    response: comparisonResponse as PublicResponseContract,
  },
];
