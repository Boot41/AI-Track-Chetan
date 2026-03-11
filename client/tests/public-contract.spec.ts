import { describe, expect, it } from "vitest";
import standardResponse from "../src/fixtures/phase0/standard_evaluation_response.json";
import { parsePublicResponseContract } from "../src/contracts/public-contract";

describe("parsePublicResponseContract", () => {
  it("accepts a valid public response payload", () => {
    const parsed = parsePublicResponseContract(standardResponse);
    expect(parsed.scorecard.title).toContain("Neon Shore");
  });

  it("rejects malformed scorecard payloads", () => {
    const malformed = {
      ...standardResponse,
      scorecard: {
        ...standardResponse.scorecard,
        risk_flags: undefined,
      },
    };
    expect(() => parsePublicResponseContract(malformed)).toThrow("Invalid response scorecard");
  });
});
