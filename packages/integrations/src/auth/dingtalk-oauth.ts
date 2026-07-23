export interface DingTalkUser {
  unionId: string;
  name: string;
  active: boolean;
}

export interface DingTalkOAuth {
  exchangeCode(code: string): Promise<{ accessToken: string }>;
  getUser(accessToken: string): Promise<DingTalkUser>;
}

interface DingTalkOAuthConfig {
  clientId: string;
  clientSecret: string;
  tokenEndpoint: string;
  userEndpoint: string;
}

type FetchLike = typeof fetch;

export class DingTalkOAuthClient implements DingTalkOAuth {
  constructor(
    private readonly config: DingTalkOAuthConfig,
    private readonly request: FetchLike = fetch,
  ) {}

  async exchangeCode(code: string): Promise<{ accessToken: string }> {
    if (!code.trim()) throw new Error("authorization code is required");
    const response = await this.request(this.config.tokenEndpoint, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        clientId: this.config.clientId,
        clientSecret: this.config.clientSecret,
        code,
        grantType: "authorization_code",
      }),
    });
    if (!response.ok) throw new Error("DingTalk code exchange failed");
    const payload = (await response.json()) as { accessToken?: string };
    if (!payload.accessToken) throw new Error("DingTalk access token missing");
    return { accessToken: payload.accessToken };
  }

  async getUser(accessToken: string): Promise<DingTalkUser> {
    const response = await this.request(this.config.userEndpoint, {
      headers: { "x-acs-dingtalk-access-token": accessToken },
    });
    if (!response.ok) throw new Error("DingTalk user lookup failed");
    const payload = (await response.json()) as {
      unionId?: string;
      nick?: string;
      active?: boolean;
    };
    if (!payload.unionId || !payload.nick) throw new Error("DingTalk user profile incomplete");
    return {
      unionId: payload.unionId,
      name: payload.nick,
      active: payload.active !== false,
    };
  }
}

