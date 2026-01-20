# Product Requirements Document: Better Booking Automation

## 1. Product Overview
**Better Booking** is a web-based automation tool designed to autonomously monitor availability and book badminton courts on the `bookings.better.org.uk` platform. It eliminates the manual effort of searching for slots by allowing users to define booking "Tasks" that the system executes using a headless browser.

## 2. Goals & Objectives
*   **Automate Availability Checks:** Continuously monitor specific leisure centres for open slots.
*   **Automated Booking:** Execute bookings immediately when criteria are met, using stored credentials and payment details.
*   **Centralized Management:** Provide a dashboard to manage booking targets (Tasks), user accounts, and payment methods.
*   **Transparency:** specific logs of all automation attempts and system activities.

## 3. User Stories
*   As a user, I want to create a **Task** specifying a date, duration, and leisure centre so the system knows what to look for.
*   As a user, I want to store my **Better.org.uk Credentials** so the system can log in on my behalf.
*   As a user, I want to save **Payment Information** so the system can complete the checkout process.
*   As a user, I want to see a list of **Successful Bookings** to confirm my court is reserved.
*   As a user, I want to view **Logs** of the system's attempts to know if it's working or if errors occurred.

## 4. Functional Requirements

### 4.1. Task Management
The core unit of work. A Task tells the bot *what* to book.
*   **Create Task:**
    *   **Select Leisure Centre:** The system *only* supports the following three locations.
    *   **Select Duration:** 40 minutes or 60 minutes.
    *   **Select Target Date.**
    *   **Court Selection:** Specific court selection is *not* supported. The system will automatically book the first available court found.
    *   **URL Generation:** The booking URL will be dynamically generated based on the selection:
        *   **Hendon Leisure Centre:** `https://bookings.better.org.uk/location/hendon-leisure-centre/badminton-{duration}/{YYYY-MM-DD}/by-time`
        *   **Barnet Copthall Leisure Centre:** `https://bookings.better.org.uk/location/barnet-copthall-leisure-centre/badminton-{duration}/{YYYY-MM-DD}/by-time`
        *   **Barnet Burnt Oak Leisure Centre:** `https://bookings.better.org.uk/location/barnet-burnt-oak-leisure-centre/badminton-{duration}/{YYYY-MM-DD}/by-time`
        *(Where `{duration}` is `40min` or `60min`)*
    *   Assign a **User Account** (for login) and **Payment Profile** to use for this task.
*   **Monitor Task:** Tasks have a status (e.g., `PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, `CANCELLED`).
*   **Task Logic:** The system must poll the website for the specified criteria.
    *   **Booking Window:** The website only shows availability within 7 days. Dates further than 7 days in the future will not have visible slots.
    *   **Release Time:** New availability is released daily at 10:00 PM.

### 4.2. User & Payment Management
*   **User Accounts:** Store `username` and `password` for `better.org.uk`.
*   **Payment Profiles:** Store payment card details required for checkout, including **Billing Address**.
*   **Relationship:** A User Account can be linked to multiple Payment Profiles (One-to-Many).

### 4.3. Booking Execution (The Bot)
*   **Headless Browser:** Use Playwright (or similar) to interact with `bookings.better.org.uk`.
*   **Workflow:**
    1.  Navigate to the specific location/activity URL.
    2.  Check for available slots matching the Task criteria.
    3.  If found, add to basket (selecting the first available court if multiple are open).
    4.  Log in using the assigned User Account.
    5.  Enter Payment Information.
    6.  Confirm Booking.
*   **Concurrency:** The system should handle multiple active tasks (sequentially or in parallel, depending on resource constraints).

### 4.4. Dashboard & Logs
*   **Status Dashboard:** View all Active Tasks and their last check time/status.
*   **Booking History:** A record of all successfully secured slots.
*   **System Logs:**
    *   **Attempt Logs:** "Checked Hendon at 10:00 AM - No slots found." / "Slot found! Attempting booking..."
    *   **Activity Logs:** "User created a new task.", "User updated payment info."

### 4.5. Authentication (App Access)
*   **Open Access:** The web application itself does *not* require a login to access. It is intended for local/private use.

## 5. Data Models

### 5.1. Entity Relationship Diagram (Conceptual)
*   **UserAccount** (1) ---- (N) **PaymentProfile**
*   **Task** (1) ---- (1) **UserAccount** (The account to book with)
*   **Task** (1) ---- (1) **PaymentProfile** (The card to use)
*   **Task** (1) ---- (0..1) **Booking** (Result)

### 5.2. Entities
*   **Task:** `id`, `location_url`, `target_date`, `target_time_start` (optional range), `target_duration`, `status`, `user_account_id`, `payment_profile_id`, `created_at`.
*   **UserAccount:** `id`, `email`, `password` (encrypted/safe storage), `name`.
*   **PaymentProfile:** `id`, `card_number`, `expiry`, `cvv`, `cardholder_name`, `user_account_id`.
*   **Booking:** `id`, `task_id`, `booking_reference`, `booked_at_time`, `details`.
*   **Log:** `id`, `timestamp`, `level` (INFO/ERROR), `message`, `related_entity_id`.

## 6. Technical Constraints & Stack
*   **Development Environment:** Windows 11 Host via Podman Containers (Linux).
*   **Deployment Environment:** Linux Containers (likely Railway).
*   **Language:** Python 3.12+.
*   **Framework:** FastHTML (Web UI), FastSQL (Database).
*   **Database:** PostgreSQL.
*   **Automation:** Playwright (Python).

## 7. Future Considerations
*   Notification integration (Telegram/Slack) upon successful booking.
*   Advanced scheduling (e.g., "Book every Tuesday").