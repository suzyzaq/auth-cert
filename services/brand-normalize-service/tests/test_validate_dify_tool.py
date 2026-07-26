from scripts.validate_dify_tool import evaluate_results


def test_evaluate_results_accepts_expected_normalization():
    result = evaluate_results(
        health={"status": "ok", "brand_count": 4249, "category_enabled": True},
        brand={
            "success": True,
            "same_brand": True,
            "matched_standard_brand_id": "BRAND_000621",
        },
        category={
            "success": True,
            "category_matched": True,
            "kind3": "陶瓷杯",
        },
        unauthorized_status=401,
    )
    assert result == {
        "status": "ok",
        "checks": {
            "health": True,
            "brand": True,
            "category": True,
            "authentication": True,
        },
    }
