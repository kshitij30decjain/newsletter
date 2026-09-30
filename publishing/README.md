# Publishing

The newsletter is rendered as HTML plus a PDF archive of that exact page:

- `newsletter.html` is the responsive inbox experience.
- `newsletter.pdf` is printed directly from that HTML for archive or download.

Do not use a PDF or image as the primary issue format. They are poor on mobile,
hide links from readers, and make the email less accessible. A PDF can be an
optional archive download after delivery.

## Render an issue

`newsletter.py` accepts the JSON result from `ResearchEvaluator.evaluate_all`
and renders its first eight selected items with source links, summaries, score,
and rationale. It does not send email or handle subscribers.

```bash
python3 -m publishing.newsletter evaluation-output.json --output-dir publishing/output
```

This creates `newsletter.html` and `newsletter.pdf`. Before delivery, replace
the literal `{unsubscribe_url}` placeholder per recipient in the HTML. The PDF
is an attachment/archive, not the email body.

## Send with Gmail

Copy `email_config.example.json` to `email_config.json`, then edit the sender,
recipient (`to`), carbon-copy (`cc`), and subject fields. The real configuration
is ignored by Git. Do not put credentials in this file.

Gmail requires a Google **App Password** (with two-step verification enabled),
not your usual Gmail password. Set it only in your shell session:

```bash
export GMAIL_APP_PASSWORD="paste-your-16-character-app-password-here"
python3 -m publishing.send_newsletter
```

The first command is preview-only and never sends mail. Once the recipients and
attachments are correct, send explicitly:

```bash
python3 -m publishing.send_newsletter --send
```

The email is constructed as `multipart/mixed`: an HTML body (with a plain
fallback for clients that cannot render HTML) plus `newsletter.pdf` attachment.
