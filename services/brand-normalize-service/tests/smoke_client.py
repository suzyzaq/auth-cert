"""真实服务冒烟测试客户端（避免 shell 中文编码问题，用 urllib 直发 UTF-8 JSON）。"""
import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8093"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else "smoke-test-token"


def post(path: str, body: dict, token: str | None = TOKEN) -> tuple[int, dict]:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


CASES = [
    ("案例1 中英文同品牌", ["HP"], ["惠普/HP"]),
    ("案例2 大小写差异", ["hp"], ["惠普/HP"]),
    ("案例3 明确不同品牌", ["Canon"], ["惠普/HP"]),
    ("案例4 附件多出品牌", ["HP", "Canon"], ["惠普/HP"]),
    ("案例5 附件品牌为空", [], ["惠普/HP"]),
    ("案例6 未知品牌", ["不存在于欧菲斯品牌库的测试品牌"], ["惠普/HP"]),
    ("案例7 两侧都为空", [], []),
]

for name, att, src in CASES:
    status, d = post("/api/brand/normalize", {
        "task_type": "brand_standardization",
        "authorization_code": "26060345263220",
        "authorization_name": "冒烟测试",
        "attachment_values": att,
        "source_values": src,
        "candidate_values": [],
        "requirements": [],
    })
    print(f"--- {name} (HTTP {status})")
    print(json.dumps({k: d[k] for k in (
        "success", "same_brand", "matched_standard_brand", "matched_standard_brand_id",
        "match_type", "confidence", "needs_manual_review",
        "attachment_unmatched_values", "attachment_extra_brands", "match_basis",
    )}, ensure_ascii=False))

# 鉴权与异常结构
status, d = post("/api/brand/normalize", {"attachment_values": ["HP"]}, token=None)
print(f"--- 无Token (HTTP {status}) success={d['success']} error_code={d['error_code']}")
status, d = post("/api/brand/reload", {})
print(f"--- reload (HTTP {status}) {json.dumps(d, ensure_ascii=False)}")
