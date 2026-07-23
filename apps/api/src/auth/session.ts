import { randomBytes, randomUUID } from "node:crypto";
import type { DingTalkOAuth } from "@auth-inspection/integrations/dingtalk-oauth";

type Role = "INSPECTOR" | "REVIEWER" | "ADMIN";

interface RoleRepository {
  findByUnionId(unionId: string): Promise<{ role: Role } | undefined>;
}

export interface CreatedSession {
  id: string;
  csrfToken: string;
  user: {
    unionId: string;
    name: string;
    role: Role;
  };
  cookie: {
    httpOnly: true;
    secure: true;
    sameSite: "strict";
    path: "/";
  };
}

export class SessionService {
  constructor(
    private readonly dingtalk: DingTalkOAuth,
    private readonly roles: RoleRepository,
  ) {}

  async create(code: string): Promise<CreatedSession> {
    const { accessToken } = await this.dingtalk.exchangeCode(code);
    const profile = await this.dingtalk.getUser(accessToken);
    if (!profile.active) throw new Error("organization account disabled");

    const role = await this.roles.findByUnionId(profile.unionId);
    if (!role) throw new Error("organization role not assigned");

    return {
      id: randomUUID(),
      csrfToken: randomBytes(32).toString("base64url"),
      user: {
        unionId: profile.unionId,
        name: profile.name,
        role: role.role,
      },
      cookie: {
        httpOnly: true,
        secure: true,
        sameSite: "strict",
        path: "/",
      },
    };
  }
}

