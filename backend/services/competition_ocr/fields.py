"""Small extraction helpers; preserve missing values instead of guessing."""
import re
from datetime import date

AWARD = r"特等奖|一等奖|二等奖|三等奖|优秀奖|优胜奖|金奖|银奖|铜奖"


def match(pattern, text, group=1):
    found = re.search(pattern, text, re.I)
    return found.group(group).strip() if found else None


def compact(text):
    return re.sub(r"\s+", "", text)


def dates(text):
    pattern = r"(?<!\d)(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})(?:日)?(?!\d)"
    for found in re.finditer(pattern, text):
        try:
            yield date(*map(int, found.groups())).isoformat()
        except ValueError:
            continue


def names(text):
    return [name for name in re.split(r"[、,，]", text or "") if re.fullmatch(r"[\u3400-\u9fff·]{2,12}", name)]


def labeled(lines, pattern, value_pattern):
    """Try text on the label row, then the immediate next OCR block."""
    for index, line in enumerate(lines):
        found = re.search(pattern, line, re.I)
        if found:
            candidate = line[found.end():].strip("：: ")
            if not candidate and index + 1 < len(lines):
                candidate = lines[index + 1]
            value = match(value_pattern, candidate)
            if value:
                return value
    return None
