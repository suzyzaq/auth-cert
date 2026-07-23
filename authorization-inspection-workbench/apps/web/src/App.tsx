import { useMemo, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell.js";
import { demoTasks } from "./data.js";
import type { RiskFilter } from "./features/tasks/TaskFilters.js";
import { DashboardPage } from "./pages/DashboardPage.js";
import { EvidenceReviewPage } from "./pages/EvidenceReviewPage.js";
import { RulesCenterPage } from "./pages/RulesCenterPage.js";
import { TaskCenterPage } from "./pages/TaskCenterPage.js";

export function App() {
  const [risk, setRisk] = useState<RiskFilter>("ALL");
  const tasks = useMemo(
    () => demoTasks.filter((task) => risk === "ALL" || task.risk === risk),
    [risk],
  );

  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route
            path="/"
            element={
              <TaskCenterPage
                tasks={tasks}
                loading={false}
                activeRisk={risk}
                onRiskChange={setRisk}
              />
            }
          />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/rules" element={<RulesCenterPage />} />
          <Route path="/tasks/:id" element={<EvidenceReviewPage />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}
