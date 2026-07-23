export interface AuthorizationChainInput {
  level: string;
  grant: string;
  authed: string;
}

export interface AuthorizationChainReview {
  needsReview: boolean;
  errorCode: "AUTHORIZATION_CHAIN_REVIEW_REQUIRED" | null;
  proposedLevel: null;
  reason: string | null;
}

export function reviewAuthorizationChain(
  input: AuthorizationChainInput,
): AuthorizationChainReview {
  const expected = Number.parseInt(input.level, 10);
  const grantCount = input.grant.split("-").filter(Boolean).length;
  const authedCount = input.authed.split("-").filter(Boolean).length;
  const needsReview =
    !Number.isInteger(expected) ||
    grantCount !== expected ||
    authedCount !== expected;

  return {
    needsReview,
    errorCode: needsReview ? "AUTHORIZATION_CHAIN_REVIEW_REQUIRED" : null,
    proposedLevel: null,
    reason: needsReview
      ? `层级${input.level}，授权方${grantCount}段，被授权方${authedCount}段`
      : null,
  };
}
