"""HTTP 和识别任务共用的数值规则，异常识别结果不直接抛 HTTP 错误。"""
from decimal import Decimal, InvalidOperation

CREDIT_MAX_HOURS = Decimal("15")
NUMBER_ERROR = "数值必须非负、有限、不超过100000且最多四位小数"


def parse_number(value):
    try:
        if isinstance(value, bool):
            raise ValueError()
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > Decimal("100000"):
            raise ValueError()
        if result != result.quantize(Decimal("0.0001")):
            raise ValueError()
        return result
    except (ValueError, InvalidOperation) as error:
        raise ValueError(NUMBER_ERROR) from error


def positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
