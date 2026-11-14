import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evaluate_zigzag import evaluate


class EvaluationReliabilityTests(unittest.TestCase):
    def make_summary(self,root,row):
        (root/"summary.json").write_text(json.dumps({
            "image_preprocessing_enabled":True,"watermark_method":"zigzag","results":[row]}),encoding="utf-8")

    def test_failed_copy_record_can_be_evaluated(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.make_summary(root,{"file":"broken.png","status":"failed","error":"invalid image",
                                    "requires_manual_review":True,"automatic_ocr_after_removal":False})
            result=evaluate(root)
            self.assertTrue(result["results"][0]["skipped"])

    def test_tampered_original_is_rejected(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/"sample";target.mkdir()
            (target/"original.png").write_bytes(b"tampered")
            self.make_summary(root,{"file":"sample.png","status":"manual_review","requires_manual_review":True,
                                    "source_sha256":hashlib.sha256(b"expected").hexdigest(),
                                    "automatic_ocr_after_removal":False})
            with self.assertRaisesRegex(ValueError,"哈希"):
                evaluate(root)


if __name__=="__main__":
    unittest.main()
