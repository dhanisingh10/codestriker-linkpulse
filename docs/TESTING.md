# Testing
Automated: run `pytest -q` in the backend folder (7 tests).
They check invalid URLs, redirects, click recording, duplicate aliases, click limits, password links, expired links and disabled links.

Manual checks:
- Create a link and open it
- Open Stats and see the click count rise
- Try a link with a click limit of 1
- Try a password-protected link
- Download a QR code
