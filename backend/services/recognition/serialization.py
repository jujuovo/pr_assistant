"""Normalize model/numpy output without accepting NaN or Infinity."""
import json


def json_safe(data):
    return json.loads(json.dumps(data, ensure_ascii=False, allow_nan=False, default=lambda value: value.tolist()))
