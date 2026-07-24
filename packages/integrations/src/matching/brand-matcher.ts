export interface MatchResult {
  raw: string;
  standardName: string | null;
  id: string | null;
  confidence: number;
  method: "EXACT" | "ALIAS" | "CANDIDATE";
}

export interface BrandMatcher {
  match(rawBrand: string): Promise<MatchResult>;
}

export class DictionaryBrandMatcher implements BrandMatcher {
  constructor(
    private readonly dictionary: Record<
      string,
      { standardName: string; id: string }
    >,
  ) {}

  async match(rawBrand: string): Promise<MatchResult> {
    const matched = this.dictionary[rawBrand.trim()];
    return matched
      ? {
          raw: rawBrand,
          standardName: matched.standardName,
          id: matched.id,
          confidence: 1,
          method: "EXACT",
        }
      : {
          raw: rawBrand,
          standardName: null,
          id: null,
          confidence: 0,
          method: "CANDIDATE",
        };
  }
}
