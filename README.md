# Better Booking Automation

A web-based automation tool to monitor and book badminton courts on `bookings.better.org.uk`.

## Features

*   **Task Management:** Create booking tasks for Hendon, Barnet Copthall, and Burnt Oak leisure centres.
*   **Automated Booking:** Uses Playwright to find slots and execute bookings automatically.
*   **Credentials Management:** Securely stores User Accounts and Payment Profiles (encrypted).
*   **Logging:** View detailed logs of automation attempts.

## Tech Stack

*   **Frontend:** FastHTML (Python)
*   **Backend:** FastSQL + PostgreSQL
*   **Automation:** Playwright (Chromium)
*   **Container:** Docker/Podman

## Getting Started

### Prerequisites
*   Docker or Podman installed.
*   `uv` (optional, for local dev).

### Setup

1.  **Clone & Configure:**
    ```bash
    git clone ...
    cd better-booking
    # Create .env file with:
    # FERNET_KEY=... (Generated on first run or use script)
    ```

2.  **Run with Docker/Podman:**
    ```bash
    podman-compose up -d --build
    ```
    The app will be available at `http://localhost:5001`.

3.  **Start the Worker:**
    The automation worker runs in the background. To start it manually inside the container:
    ```bash
    podman exec -d better_booking_web uv run python bot.py
    ```

## Usage

1.  **Settings:** Go to `/settings` and add a User Account and Payment Profile (including Billing Address).
2.  **Create Task:** Go to `/tasks/new` and schedule a task (within the next 7 days).
3.  **Monitor:** Check the Dashboard (`/`) for status and `/logs` for details.

## Security Note
*   Payment and Password data is encrypted using Fernet symmetric encryption.
*   Ensure `FERNET_KEY` is kept secret and persistent across restarts to decrypt data.