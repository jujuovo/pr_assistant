from dataclasses import dataclass
from src.lab_io import ROOT, SAMPLES, IMAGE_EXTENSIONS


@dataclass(frozen=True)
class Category:
    key: str
    name: str
    source_folder: str
    sample_folder: str
    kind: str


CATEGORIES = {category.key: category for category in (
    Category("lanqiao", "蓝桥杯", "Lanqiao Cup", "LanqiaoCup", "competition"),
    Category("computer-design", "中国大学生计算机设计大赛", "计算机设计大赛", "ComputerDesign", "competition"),
    Category("software-design", "中国软件杯大学生软件设计大赛", "软件设计大赛", "SoftwareDesign", "competition"),
    Category("challenge-cup", "挑战杯创业计划竞赛", "挑战杯-创业计划竞赛", "ChallengeCup", "competition"),
    Category("csp", "CCF CSP 认证", "CSP", "CSP", "certification"),
    Category("social-practice", "社会实践", "社会实践", "SocialPractice", "practice"),
    Category("other", "其他证明", "其他", "Other", "other"),
)}


def category(key):
    if key not in CATEGORIES:
        raise ValueError(f"未知类别：{key}")
    return CATEGORIES[key]
