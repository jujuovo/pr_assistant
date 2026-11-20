"""信息学院2025年2月办法第4、10页及附件1，适用于2028届起。"""
from decimal import Decimal

POLICY_VERSION = "information-college-research-2025-02"
CHINESE_JOURNALS = frozenset("""
软件学报
计算机学报
中国科学：信息科学
计算机研究与发展
计算机辅助设计与图形学学报
电子学报
自动化学报
通信学报
电子与信息学报
声学学报
""".strip().splitlines())

INTERNATIONAL_JOURNALS = frozenset("""
IEEE Journal on Selected Areas in Communications
IEEE Transactions on Wireless Communications
IEEE Transactions on Communications
IEEE Transactions on Antennas and Propagation
IEEE Wireless Communications
IEEE Transactions on Multimedia
IEEE Transactions on Broadcasting
IEEE Transactions on Aerospace and Electronic Systems
IEEE Signal Processing Magazine
IEEE Transactions on Medical Imaging
IEEE Transactions on Power Electronics
IEEE Transactions on Signal Processing
IEEE Transactions on Microwave Theory and Techniques
IEEE Transactions on Neural Networks and Learning Systems
IEEE Transactions on Intelligent Transportation Systems
IEEE Transactions on Circuits and Systems for Video Technology
IEEE Transactions on Industrial Electronics
IEEE Journal of Selected Topics in Signal Processing
IEEE Transactions on Vehicular Technology
IEEE Transactions on Computational Imaging
IEEE Journal of Selected Topics in Quantum Electronics
IEEE Transactions on Biomedical Engineering
IEEE Transactions on Terahertz Science and Technology
IEEE Transactions on Image Processing
IEEE Transactions on Knowledge and Data Engineering
IEEE Transactions on Mobile Computing
IEEE Transactions on Informfation Forensics and Security
IEEE/ACM Transactions on Networking
""".strip().splitlines())


def paper_bases(facts):
    """Return every supported directory match using teacher-verified facts."""
    venue = facts["venue"]
    matches = []
    if facts.get("ccf_grade") in ("A", "B", "C"):
        if facts.get("ccf_version") and facts.get("ccf_entry") == venue:
            grade = facts["ccf_grade"]
            matches.append(({"A": 10, "B": 6, "C": 1}[grade], "CCF-" + grade))
    if venue in CHINESE_JOURNALS:
        matches.append((6, "附件1第三项"))
    if venue in INTERNATIONAL_JOURNALS:
        matches.append((10, "附件1第四项"))
    family = facts.get("verified_family")
    if venue in ("Nature", "Science", "Cell"):
        matches.append((20, "附件1第一项主刊"))
    elif family in ("Nature", "Science", "CELL") and venue.upper().startswith(family.upper()):
        if family != "CELL" or (facts.get("if_year") == 2025
                                and Decimal(str(facts["impact_factor"])) >= 10):
            matches.append((20, "附件1第一项子刊"))
    return matches


def candidate(category, facts, cutoff):
    """Calculate from normalized facts. Date strings use ISO YYYY-MM-DD."""
    if facts["first_institution"] != "厦门大学":
        return Decimal(0), "厦门大学不是第一单位"
    paper = category == "research_paper"
    if not paper and not facts["authorized_national_invention"]:
        return Decimal(0), "未取得国家发明专利授权"
    evidence_date = facts["proof_date" if paper else "certificate_date"]
    if evidence_date > cutoff:
        return Decimal(0), "超过推免当年8月31日"
    basis, base = "授权发明专利", 2
    if paper:
        if not (facts["published"] and facts["indexed"]):
            return Decimal(0), "未同时满足发表与收录条件"
        if facts["article_type"] not in ("long_article", "full_article"):
            return Decimal(0), "文章类型不符合长文或正文条件"
        matches = paper_bases(facts)
        if not matches:
            return Decimal(0), "未命中核定目录"
        base, basis = max(matches)
    authors = [author for author in facts["authors"] if author != facts.get("mentor")]
    student = facts["student_author"]
    if student not in authors:
        return Decimal(0), "未列入可计分作者"
    rank = authors.index(student) + 1
    if len(authors) == 1:
        coefficient = Decimal(1)
    elif paper and rank <= 2 and all(author in facts["cofirst_authors"] for author in authors[:2]):
        coefficient = Decimal("0.5")
    elif rank == 1:
        coefficient = Decimal("0.8")
    elif paper and rank == 2:
        coefficient = Decimal("0.2")
    else:
        return Decimal(0), "作者顺位超出计分范围"
    return base * coefficient, basis
