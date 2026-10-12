"""按材料类型注册提取器，后续证书适配器复用同一批次/证据框架。"""
from .volunteer import extract

ADAPTER_VERSION = "volunteer-3"
ADAPTERS = {"volunteer_credit": (extract, "credit"), "volunteer_honor": (extract, "honor")}


def recognize_fields(material_type, data, width, claimed_hours=None):
    adapter, expected_page = ADAPTERS[material_type]
    report = adapter(data, width, claimed_hours)
    report["adapter_version"] = ADAPTER_VERSION
    if report.get("page_type") != expected_page:
        report["warnings"].append({"code": "wrong_material_type", "message": "图片页面与上传时选择的信用/荣誉类型不一致"})
    return report
