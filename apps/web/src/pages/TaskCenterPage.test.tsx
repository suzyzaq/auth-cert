// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { TaskCenterPage } from "./TaskCenterPage.js";

function renderPage(element: ReactNode) {
  return render(<MemoryRouter>{element}</MemoryRouter>);
}

describe("TaskCenterPage", () => {
  it("filters the task list by risk", async () => {
    const user = userEvent.setup();
    const onFilterChange = vi.fn();
    renderPage(
      <TaskCenterPage
        tasks={[]}
        loading={false}
        activeRisk="ALL"
        onRiskChange={onFilterChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: /严重/ }));

    expect(onFilterChange).toHaveBeenCalledWith("CRITICAL");
  });

  it("shows task evidence summary", () => {
    renderPage(
      <TaskCenterPage
        tasks={[
          {
            id: "task-babycare",
            brand: "BABYCARE",
            code: "26062914254888",
            name: "BABYCARE-商标注册证书",
            status: "REVIEW_REQUIRED",
            risk: "CRITICAL",
            issueCount: 2,
            assignee: "待分配",
            updatedAt: "2026-07-23 16:20",
          },
        ]}
        loading={false}
        activeRisk="ALL"
        onRiskChange={() => undefined}
      />,
    );

    expect(screen.getByText("BABYCARE")).toBeInTheDocument();
    expect(screen.getByText("2 项异常")).toBeInTheDocument();
  });
});
