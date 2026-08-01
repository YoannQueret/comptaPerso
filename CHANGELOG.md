# Changelog

All notable changes to this project are documented in this file.

The format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions are tracked in the `VERSION` file at the repo root.

## [0.3.2] - 2026-08-01

### Added
- The transactions page now shows the selected account's real balance,
  right under the account filter dropdown.

## [0.3.1] - 2026-07-31

### Fixed
- Static files (JS/CSS) are now served with `Cache-Control: no-cache, max-age=0`,
  forcing the browser to always revalidate against the server (a cheap
  conditional request, 304 if unchanged) instead of trusting its own
  heuristic cache lifetime. Some browsers (Chrome on Android in particular)
  could otherwise keep serving a stale script long after a deploy, with no
  way to recover short of the user manually clearing their cache.

## [0.3.0] - 2026-07-30

### Added
- Per-user currency management (Settings → Currencies): each user gets their
  own list of currencies (seeded with EUR, CHF, USD, GBP — only EUR active by
  default), with the ability to activate/deactivate or add new ones. Account
  creation/edit only offers active currencies.
- A currency in use by at least one account can't be deactivated or deleted —
  enforced server-side, and the corresponding buttons are hidden from the UI
  entirely rather than shown and failing.
- Migration seeds existing users' currency lists from their real data: any
  currency already used by one of their accounts is activated automatically,
  in addition to the EUR default, so nothing already in use is silently
  hidden after upgrading.

## [0.2.2] - 2026-07-30

### Added
- Transfers merged into the Transactions page: "+ Add" split into "Add a
  transaction" / "Add a transfer", transfer rows editable directly from the
  table. The standalone Transfers page and nav link are gone.
- The selected account is now remembered for the session and stays the same
  when navigating between Transactions, Budget, Reports, and add/edit forms,
  instead of resetting to the default account every time.
- Photo attachments are resized and re-encoded client-side before upload
  (phone camera photos are routinely 8-12 MB); PDFs and already-small files
  are left untouched.

### Fixed
- The budget-month calendar picker was invisible inside the add-transaction/
  add-transfer popups (a `<dialog>` opened via `showModal()` sits in the
  browser's top layer, so the picker rendered behind it).
- The balance chart now selects transactions by budget month, like the
  summary cards, instead of by real date — a budget-shifted transaction no
  longer disappears from one or the other, and the chart's ending balance
  reconciles exactly with "net balance (with carryover)" plus the remaining
  forecast.
- "Remaining to live on (forecast)" no longer duplicates "Net balance"; its
  hint text now says explicitly that it excludes the previous month's
  carryover (the value the balance chart's ending point does include).

### Changed
- Monthly budget summary cards tidied: income/expenses/net merged into one
  compact receipt-style card instead of three separate ones.

## [0.2.0] - 2026-07-26

Initial tracked version. Self-hosted, multi-user personal finance tracker
built with Flask:

- Multi-currency accounts, categories/subcategories, transactions, and
  inter-account transfers (including cross-currency, with separate sent/
  received amounts).
- Recurring expenses/income with adjustable monthly validation, including
  recurring transfers.
- A budget-month concept decoupled from the real transaction date, so an
  operation near a month boundary can be attributed to the intended month.
- Monthly budget view with a day-by-day balance projection chart, and
  period/month-by-month/year-by-year reports.
- Password reset via email (SMTP configurable through environment
  variables), self-service registration (can be disabled).
- French/English interface.
- Mobile-friendly tables (stacked-card layout), instant client-side table
  search, inline attachment preview popup.
- Docker (SQLite or MariaDB) and plain-Python deployment, with automatic
  pre-migration SQLite backups.
