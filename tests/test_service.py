"""
Unit tests for services.inference_service
"""

import time
import unittest
from services.inference_service import InferenceService


class TestInferenceService(unittest.TestCase):

    def setUp(self):
        self.service = InferenceService(fake_mode=True)

    def test_submit_and_poll_job(self):
        job = self.service.submit_job(
            image_path="test_image.jpg",
            bbox=[10, 10, 200, 400]
        )
        self.assertIsNotNone(job.job_id)
        self.assertIn(job.status, ["queued", "running", "succeeded"])

        # Wait for completion
        for _ in range(50):
            if job.status == "succeeded":
                break
            time.sleep(0.05)

        self.assertEqual(job.status, "succeeded")
        self.assertEqual(job.progress, 1.0)
        self.assertIsNotNone(job.result)

    def test_job_isolation(self):
        job1 = self.service.submit_job("img1.jpg")
        job2 = self.service.submit_job("img2.jpg")

        self.assertNotEqual(job1.job_id, job2.job_id)

        # Poll both
        for _ in range(50):
            if job1.status == "succeeded" and job2.status == "succeeded":
                break
            time.sleep(0.05)

        self.assertEqual(job1.status, "succeeded")
        self.assertEqual(job2.status, "succeeded")

    def test_get_nonexistent_job(self):
        res = self.service.get_job("nonexistent_id_12345")
        self.assertIsNone(res)

    def test_api_health_endpoint(self):
        try:
            from webui.app import app
        except ImportError:
            self.skipTest("Flask not installed in this Python environment (e.g. mayapy).")
        with app.test_client() as client:
            resp = client.get("/api/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertEqual(data.get("status"), "ok")

    def test_api_succeeded_job_dto_and_no_500(self):
        """
        AUD-09 Acceptance:
        Ensures a succeeded job does not trigger 500 error due to started_at
        and returns complete DTO contract (v2 json, skeleton data, latency).
        """
        job = self.service.submit_job("test_img.jpg")
        for _ in range(50):
            if job.status == "succeeded":
                break
            time.sleep(0.05)
        self.assertEqual(job.status, "succeeded")

        try:
            from webui.app import app
        except ImportError:
            self.skipTest("Flask not installed in this Python environment (e.g. mayapy).")
        with app.test_client() as client:
            resp = client.get(f"/api/jobs/{job.job_id}")
            self.assertEqual(resp.status_code, 200, f"Expected 200 OK, got {resp.status_code}: {resp.data}")
            data = resp.get_json()
            self.assertIn("result", data)
            dto = data["result"]
            self.assertTrue(dto.get("success"))
            self.assertIsInstance(dto.get("latency_seconds"), (int, float))
            self.assertIsNotNone(dto.get("json_url"))
            self.assertIsNotNone(data.get("skeleton"))


if __name__ == '__main__':
    unittest.main()
