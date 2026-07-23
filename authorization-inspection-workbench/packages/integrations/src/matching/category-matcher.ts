import type { MatchResult } from "./brand-matcher.js";

export interface CategoryContext {
  brand?: string;
  authorizationType?: string;
  sourcePath?: string;
}

export interface CategoryMatcher {
  match(rawCategory: string, context: CategoryContext): Promise<MatchResult>;
}

export class DictionaryCategoryMatcher implements CategoryMatcher {
  constructor(
    private readonly dictionary: Record<
      string,
      { standardName: string; id: string }
    >,
  ) {}

  async match(
    rawCategory: string,
    _context: CategoryContext,
  ): Promise<MatchResult> {
    const matched = this.dictionary[rawCategory.trim()];
    return matched
      ? {
          raw: rawCategory,
          standardName: matched.standardName,
          id: matched.id,
          confidence: 1,
          method: "EXACT",
        }
      : {
          raw: rawCategory,
          standardName: null,
          id: null,
          confidence: 0,
          method: "CANDIDATE",
        };
  }
}
