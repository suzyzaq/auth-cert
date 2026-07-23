import type { FastifyInstance } from "fastify";

export const taskFixtures = [
  {
    id: "task-babycare",
    brand: "BABYCARE",
    code: "26062914254888",
    name: "BABYCARE-商标注册证书",
    status: "REVIEW_REQUIRED",
    risk: "CRITICAL",
    issueCount: 2,
    fields: ["effectiveDate", "expiryDate"],
    assignee: "待分配",
    updatedAt: "2026-07-23 16:20",
  },
  {
    id: "task-yinbabei",
    brand: "印芭贝",
    code: "26071319475337",
    name: "印芭贝-商标注册证书",
    status: "REVIEW_REQUIRED",
    risk: "CRITICAL",
    issueCount: 2,
    fields: ["effectiveDate", "expiryDate"],
    assignee: "张复核",
    updatedAt: "2026-07-23 16:18",
  },
  {
    id: "task-hengjingsen",
    brand: "恒净森",
    code: "26071315192350",
    name: "恒净森-商标注册证书",
    status: "REVIEW_REQUIRED",
    risk: "CRITICAL",
    issueCount: 1,
    fields: ["effectiveDate"],
    assignee: "李巡检",
    updatedAt: "2026-07-23 16:16",
  },
  {
    id: "task-hoyo",
    brand: "HOYO",
    code: "26042212341521",
    name: "HOYO授权书",
    status: "REVIEWED",
    risk: "LOW",
    issueCount: 0,
    fields: [],
    assignee: "王复核",
    updatedAt: "2026-07-23 16:12",
  },
];

export async function registerTaskRoutes(app: FastifyInstance) {
  app.get("/api/tasks", async (request) => {
    const query = request.query as {
      risk?: string;
      status?: string;
      keyword?: string;
    };
    const items = taskFixtures.filter((task) => {
      if (query.risk && task.risk !== query.risk) return false;
      if (query.status && task.status !== query.status) return false;
      if (
        query.keyword &&
        !`${task.brand}${task.code}${task.name}`
          .toLowerCase()
          .includes(query.keyword.toLowerCase())
      ) {
        return false;
      }
      return true;
    });
    return { total: items.length, items };
  });

  app.get("/api/tasks/:id", async (request, reply) => {
    const { id } = request.params as { id: string };
    const task = taskFixtures.find((item) => item.id === id);
    if (!task) return reply.code(404).send({ message: "task not found" });
    return {
      ...task,
      comparisons:
        id === "task-hoyo"
          ? [
              {
                field: "effectiveDate",
                label: "生效日期",
                sourceValue: "",
                proposedValue: "",
                confidence: 0.96,
                decision: "附件未明确，保持为空",
              },
            ]
          : [
              {
                field: "effectiveDate",
                label: "生效日期",
                sourceValue: "2032-09-07",
                proposedValue: "2022-09-07",
                confidence: 0.99,
                decision: "建议修正",
              },
              {
                field: "expiryDate",
                label: "失效日期",
                sourceValue: "2022-09-06",
                proposedValue: "2032-09-06",
                confidence: 0.99,
                decision: "建议修正",
              },
            ],
      evidence: {
        page: 1,
        text: "注册日期 2022年09月07日 有效期至 2032年09月06日",
      },
    };
  });
}
