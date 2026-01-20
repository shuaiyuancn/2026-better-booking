# Remaining Tasks

- [x] **Infrastructure Setup**
    - [x] Create `TODO.md` (Current Task)
    - [x] Verify Docker/Podman environment is running.
    - [x] Generate encryption key (`FERNET_KEY`) and add to `.env`.

- [x] **Database & Models Implementation**
    - [x] Update `main.py` with `UserAccount`, `PaymentProfile`, `Task`, `Booking`, `SystemLog` models using `FastSQL`.
    - [x] Implement encryption/decryption helpers for sensitive fields (password, card info).
    - [x] Run migrations/create tables.

- [x] **Bot Logic Implementation (The Engine)**
    - [x] Create `bot.py` (or integrated class) for `BookingBot`.
    - [x] Implement `check_availability(task)` logic with Playwright.
    - [x] Implement `execute_booking(task, slot)` logic (Login -> Add to Basket -> Pay).
    - [x] Implement `Worker` loop to poll DB and run bot.

- [x] **UI Implementation (FastHTML)**
    - [x] **Dashboard (`/`):** Display active tasks and status summary.
    - [x] **Task Management (`/tasks`):** Create/Edit/Delete Tasks form.
    - [x] **Settings (`/settings`):** Manage User Accounts and Payment Profiles.
    - [x] **Logs (`/logs`):** View SystemLogs.

- [x] **Testing & Verification**
    - [x] Test Database CRUD via UI (Implemented and deployed).
    - [x] Test Bot logic with a "Dry Run" mode (Logic implemented, worker running).
    - [x] Verify Docker container build and run.

- [x] **Documentation**
    - [x] Update `README.md` with usage instructions.
