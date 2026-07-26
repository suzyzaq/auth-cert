from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_host_port_can_be_changed_without_changing_container_port():
    compose = yaml.safe_load(
        (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    ports = compose["services"]["brand-normalize"]["ports"]
    assert ports == ["${BRAND_HOST_PORT:-8000}:8000"]


def test_image_contains_category_fallback_rules():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY config ./config" in dockerfile
