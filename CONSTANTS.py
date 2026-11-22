import os

BASE_URL = "https://cq-screen.bhairav.workers.dev/"
AUTH_ENDPOINT_POST = "auth/start"
ASSETS_ENDPOINT_GET = "s2/assets"
DEPLOY_ENDPOINT_POST = "s2/deploy"
REPORT_ENDPOINT_POST = "s2/report"
# Per-candidate key for the screening server. Read from the environment, never committed.
MY_KEY = os.environ.get("CQ_CANDIDATE_KEY", "")

IDEMPOTENCY_HEADER = "X-CQ-Idempotency-Key"
USER_AGENT = "Mozilla/5.0 (compatible; cq-screen-client/1.0; +candidate-submission)"

PAGE_SIZE = 25

# Refresh the bearer token before it actually expires (server said expires_in=300s).
# Refresh at 80% of the *actual* expires_in returned each time, never a hardcoded constant.
TOKEN_REFRESH_FRACTION = 0.8

# Stop issuing *new* writes once run_minutes_remaining drops to/below this,
# so there's guaranteed time left to resolve ambiguous attempts and build+send the report.
STOP_NEW_WRITES_MINUTES = 15
# Hard stop for *everything* (including ambiguous-resolution retries) - past this,
# whatever's unresolved gets reported blocked rather than guessed as deployed.
HARD_STOP_MINUTES = 5

JOURNAL_DB_PATH = "journal.sqlite3"
