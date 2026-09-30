import unittest
from datetime import date
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from publishing.newsletter import render_newsletter, write_newsletter


class NewsletterRendererTests(unittest.TestCase):
    def test_renders_html_and_plain_text_from_evaluator_payload(self):
        payload = {
            "items": [
                {
                    "name": "Example <Model>",
                    "type": "model",
                    "final_score": 91.25,
                    "reason": "Useful for <teams>.",
                    "research": {
                        "github": {
                            "repository": "org/example-repo",
                            "url": "https://github.com/org/example-repo",
                        },
                        "huggingface": {
                            "model": "org/example",
                            "url": "https://huggingface.co/org/example",
                            "readme": "A **safe** summary.",
                        }
                    },
                }
            ]
        }

        html_body, text_body = render_newsletter(payload, issue_date=date(2026, 9, 28))

        self.assertIn("Example &lt;Model&gt;", html_body)
        self.assertNotIn("Example <Model>", html_body)
        self.assertIn("https://huggingface.co/org/example", html_body)
        self.assertIn("A safe summary.", text_body)
        self.assertIn("<strong>91.2/100</strong>", html_body)
        self.assertIn("Hugging Face downloads", html_body)
        self.assertIn("↓ 0", html_body)
        self.assertIn("Sources:", html_body)
        self.assertIn("https://github.com/org/example-repo", html_body)
        self.assertIn("https://huggingface.co/org/example", html_body)

    def test_reads_items_from_saved_stage_file(self):
        payload = {
            "stage": "evaluation",
            "result": {
                "items": [{"name": "Wrapped", "type": "tag", "final_score": 80, "reason": "Saved stage."}]
            },
        }

        html_body, _text_body = render_newsletter(payload, issue_date=date(2026, 9, 30))

        self.assertIn("Wrapped", html_body)
        self.assertIn("Saved stage.", html_body)

    def test_rejects_empty_issue(self):
        with self.assertRaisesRegex(ValueError, "without selected items"):
            render_newsletter({"items": []})

    def test_writes_html_and_exports_the_same_page_to_pdf(self):
        payload = {"items": [{"name": "One", "type": "tag", "final_score": 75}]}

        with TemporaryDirectory() as directory, patch("publishing.newsletter.html_to_pdf") as export:
            html_path, pdf_path = write_newsletter(payload, Path(directory))

        self.assertEqual(html_path.name, "newsletter.html")
        self.assertEqual(pdf_path.name, "newsletter.pdf")
        self.assertTrue(export.called)
        self.assertEqual(export.call_args.args, (html_path, pdf_path))


if __name__ == "__main__":
    unittest.main()
