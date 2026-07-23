// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AppShell } from "../components/AppShell.js";
import { RulesCenterPage } from "./RulesCenterPage.js";

describe("RulesCenterPage", () => {
  it("filters rules and shows rule details", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <RulesCenterPage />
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText("搜索规则"), "边界分片");

    expect(
      screen.getByRole("heading", { name: "边界分片探测" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("授权日期顺序")).not.toBeInTheDocument();
    expect(screen.getByText("shard/{shardCount}.json 状态不是 404")).toBeInTheDocument();
  });

  it("opens the public database without passing internal context", () => {
    render(
      <MemoryRouter>
        <AppShell>
          <div />
        </AppShell>
      </MemoryRouter>,
    );

    const link = screen.getByRole("link", { name: "授权资质数据库" });
    expect(link).toHaveAttribute(
      "href",
      "https://suzyzaq.github.io/auth-cert-db/",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
});
