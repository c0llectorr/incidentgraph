"""Migration 0002: add the discount_codes table.

Deployment note (2026-10-02 release): this migration must be applied before
the checkout change ships; the ops runbook lists it as a manual step. If it
has not run, the registry in app/main.py falls back to built-in codes only.
"""

CREATE_DISCOUNT_CODES = """
CREATE TABLE IF NOT EXISTS discount_codes (
    code TEXT PRIMARY KEY,
    percent_off INTEGER NOT NULL,
    expires_on DATE
)
"""

INSERT_LAUNCH_CODES = """
INSERT OR IGNORE INTO discount_codes (code, percent_off, expires_on)
VALUES ('WELCOME10', 10, NULL), ('LAUNCH25', 25, '2026-12-31')
"""


def apply(connection) -> None:
    connection.execute(CREATE_DISCOUNT_CODES)
    connection.execute(INSERT_LAUNCH_CODES)
    connection.commit()
