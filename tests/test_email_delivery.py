import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from publishing.send_newsletter import build_message, load_config


class NewsletterEmailTests(unittest.TestCase):
    def test_builds_html_body_and_pdf_attachment(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "email.json"
            html_path = root / "newsletter.html"
            pdf_path = root / "newsletter.pdf"
            config_path.write_text(json.dumps({
                "gmail": {"sender": "sender@example.com"},
                "to": ["reader@example.com"],
                "cc": ["copy@example.com"],
                "subject": "Weekly issue",
            }), encoding="utf-8")
            html_path.write_text("<h1>AI Signal</h1>", encoding="utf-8")
            pdf_path.write_bytes(b"%PDF-test")

            message = build_message(load_config(config_path), html_path, pdf_path)

        self.assertEqual(message["To"], "reader@example.com")
        self.assertEqual(message["Cc"], "copy@example.com")
        self.assertTrue(message.is_multipart())
        self.assertEqual(message.get_body("html").get_content().strip(), "<h1>AI Signal</h1>")
        attachment = next(message.iter_attachments())
        self.assertEqual(attachment.get_content_type(), "application/pdf")
        self.assertEqual(attachment.get_filename(), "newsletter.pdf")


if __name__ == "__main__":
    unittest.main()
