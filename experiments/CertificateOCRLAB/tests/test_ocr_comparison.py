import unittest
from src.ocr_comparison import compare_ocr_fields

class OCRComparisonTests(unittest.TestCase):
    def test_award_lost_after_preprocessing_is_flagged(self):
        report=compare_ocr_fields(["福建赛区二等奖。"],["福建赛区等奖。"])
        self.assertEqual(report["differences"][0]["status"],"lost_after_preprocessing")
        self.assertEqual(report["differences"][0]["field"],"award")
        self.assertTrue(report["requires_manual_review"])

    def test_different_school_remains_two_candidates(self):
        report=compare_ocr_fields(["学校名称：厦学"],["学校名称：厦门大学"])
        self.assertEqual(report["raw_fields"]["school"],"厦学")
        self.assertEqual(report["processed_fields"]["school"],"厦门大学")
        self.assertEqual(report["differences"][0]["status"],"disagreement")

    def test_numeric_noise_is_not_appended_to_certificate(self):
        report=compare_ocr_fields(["证书编号：1234567801"],
                                  ["证书编号：1234567801","5"])
        self.assertEqual(report["processed_fields"]["certificate_no"],"1234567801")
        self.assertEqual(report["differences"],[])

    def test_split_name_and_date_are_joined(self):
        report=compare_ocr_fields(["学生姓名：","张三","2026年5月8","日"],
                                  ["学姓名张三","2026年5月8日"])
        self.assertEqual(report["raw_fields"]["student"],"张三")
        self.assertEqual(report["processed_fields"]["date"],"2026年5月8日")
        self.assertEqual(report["differences"],[])

if __name__=="__main__":
    unittest.main()
