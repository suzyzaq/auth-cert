export const retryPolicy = {
  attempts: 3,
  backoff: {
    type: "exponential" as const,
    delay: 1_000,
  },
};
