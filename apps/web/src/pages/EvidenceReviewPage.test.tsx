// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { EvidenceReviewPage } from "./EvidenceReviewPage.js";

describe("EvidenceReviewPage", () => {
  it("shows source, attachment and page-level evidence in clear Chinese", () => {
    render(
      <MemoryRouter initialEntries={["/tasks/task-babycare"]}>
        <Routes>
          <Route path="/tasks/:id" element={<EvidenceReviewPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "字段重建与核对" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("数据库原值")).toHaveLength(3);
    expect(screen.getAllByText("附件重建值")).toHaveLength(3);
    expect(screen.getAllByText("附件第 1 页")).toHaveLength(3);
    expect(screen.getAllByText("96%").length).toBeGreaterThan(1);
    expect(screen.getAllByText("建议修正")).toHaveLength(2);
  });
});
