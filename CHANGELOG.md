# Changelog

All notable changes to this project are documented in this file.

The format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions are tracked in the `VERSION` file at the repo root.

## [0.4.2] - 2026-09-02

### Added
- A "Profile" submenu (top-right user menu) to set your display timezone.
  It's used to show dates/times (last login, invitations...) in your own
  local time, and — more importantly — to determine "today" throughout the
  app (the real/current balance, "future transaction" highlighting, default
  dates, overdue rules, report periods) independently of the server's own
  timezone. A user ahead of the server (e.g. server in UTC, user in
  Europe/Paris) now sees their day roll over at their own local midnight,
  not the server's.
- The balance chart's hover tooltip now lists each operation's own amount
  alongside its label, not just the running balance. Several transactions
  landing on the same day are grouped into a single tooltip instead of only
  showing whichever one the mouse happened to land nearest to.

## [0.4.1] - 2026-08-26

### Added
- A "reviewed" tick mark next to the amount, on both the transactions page
  and the monthly budget page's tables — a shared checklist aid with no
  effect on any balance/report. Persisted server-side, so it's kept across
  reloads and visible to anyone with access to the account (including a
  shared account's collaborators).

### Changed
- On the monthly budget page, both the validated recurrences and the other
  transactions tables now sort by date, most recent first.

### Fixed
- Amount fields (transactions, transfers, recurring rules) now tolerate
  whatever a bank statement or a non-English keyboard produces — a comma
  decimal separator, a space/apostrophe/dot thousands separator (e.g. Swiss
  "1'234.50"), a stray currency symbol — instead of crashing with an
  "Internal Server Error" on anything that wasn't a plain "1234.56". A
  genuinely invalid amount now shows a clear validation message instead.

## [0.4.0] - 2026-08-09

### Added
- Account sharing: an account owner can share one of their accounts with
  another existing user, either read-only or read-write, from the Accounts
  page ("Partager" button, with a "Shared with me" section listing what
  others have shared with you).
  - Read-write lets a collaborator add/edit/delete transactions and transfers
    on the account, and manage/validate its recurring rules — never rename,
    delete, or change the account's type/currency, which stay owner-only.
  - A shared account behaves like a normal one everywhere it's used
    (dashboard, transactions, monthly budget, reports), using the *owner's*
    categories so the owner's own budget/reports stay coherent regardless of
    who actually recorded a transaction.
  - Transfers between one of your own accounts and an account shared with you
    (write) are supported, even across two different owners.
  - Sharing requires the recipient to already have an account on the
    instance; an unknown email is rejected with a clear error.
  - Revoking a share takes effect immediately on the collaborator's next
    request.
- On the dashboard, shared accounts are visually distinguished (light blue
  background), always listed after your own accounts, and only show the
  "add transaction" shortcut when you have write access. The account's type
  now sits on its own line under the account name.
- The "add transaction" account picker (dashboard, transactions page, monthly
  budget) now labels a shared account with its owner's name.

### Fixed
- Closed a latent gap where a posted account id on the transaction/recurring
  forms was never checked against the current user before use — harmless
  while data was fully siloed, but a real cross-account write risk now that
  accounts can be shared.

## [0.3.5] - 2026-08-09

### Added
- Admin "Invitations" submenu: tracks every invite sent (send date, expiration,
  whether it was turned into an account) and lets you resend one, which issues
  a new link and restarts its expiration clock. The invite form moved here
  from the Users page.
- The Users page now shows both "last authentication" (password login) and
  "last activity" (any authenticated request), instead of one ambiguous "last
  login" column that only reflected the former.
- README documents that the first account created on an install gets admin
  rights automatically.
- README_FR.md: a maintained French translation of the README.
- A visual-only checkbox next to the amount in the monthly budget's validated
  recurrences and other-transactions tables, for manually ticking things off
  while reviewing — no state saved.
- `SESSION_IDLE_TIMEOUT`: logs a user out after a configurable period of
  inactivity (default 20 minutes, `0` to disable).

### Changed
- Navbar dropdowns (Settings, Administration, account menu) are now mutually
  exclusive — opening one closes the others.

### Fixed
- CSRF tokens no longer expire after Flask-WTF's default 1 hour regardless of
  the session — they now stay valid for the life of the session, since the
  old default was rejecting legitimate submissions (e.g. a transaction form
  left open over lunch). A friendly message + redirect now also replaces the
  raw "Bad Request" page for the remaining edge cases (token really invalid).

## [0.3.4] - 2026-08-03

### Fixed
- The "upcoming recurrences" count shown on the dashboard's monthly budget
  button now matches what the monthly budget page actually displays: it's
  scoped to the same account and uses the real end-of-month date instead of
  a fixed day-28 approximation. The count is now also labeled "recurrence(s)"
  instead of showing a bare number.

## [0.3.3] - 2026-08-02

### Added
- Administrator role: the first account ever created becomes an admin. Admins
  get an "Administration" menu (top right, next to Settings) with a user list
  showing each account's role and last login, but not their financial data.
- Admins can promote/demote other accounts to admin (at least one admin must
  always remain, and you can't remove your own admin rights), delete a user
  account (cascades their data, can't delete yourself), and deactivate/
  reactivate an account without deleting it — a deactivated user is signed
  out immediately and can't log back in until reactivated.
- Admins can invite new users by email even when self-service registration is
  disabled, using the same expiring signed-link mechanism as password reset.
- On the transactions page, filtering by a parent category now also includes
  transactions filed under its child categories.

### Changed
- The mobile navigation menu now opens as a proper overlay panel (card
  background, shadow, larger touch targets) instead of a plain stack of
  small links.

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
