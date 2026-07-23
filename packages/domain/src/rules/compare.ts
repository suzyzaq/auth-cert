export function valuesDiffer(
  sourceValue: unknown,
  proposedValue: unknown,
): boolean {
  return JSON.stringify(sourceValue) !== JSON.stringify(proposedValue);
}
