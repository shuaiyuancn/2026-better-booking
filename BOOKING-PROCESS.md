# Booking Process Analysis

This document outlines the step-by-step process for automating bookings on `bookings.better.org.uk`, verified with a live test.

## 1. Availability Search
**URL Pattern:** `https://bookings.better.org.uk/location/{slug}/badminton-{duration}/{YYYY-MM-DD}/by-time`

*   **Page Load:**
    *   **Cookie Consent:** Click "Accept All Cookies" button (`button:has-text("Accept All Cookies")`).
    *   **No Availability:** Check for text "No results were found at this centre".
*   **Slot Detection:**
    *   Available slots appear as links (e.g., "Ad Hoc session...").
    *   Example Selector: `a[href*="/slot/"]`.
    *   **Time Matching:** The link text or href contains the start/end time (e.g., `07:00-07:40`).
*   **Action:** Click the slot element.

## 2. Slot Selection (Modal)
*   **State:** A modal or overlay appears with "Your selection".
*   **Court Selection:**
    *   Check if "Book now" button is disabled.
    *   Check if text "The session being booked is already full" is visible.
    *   **If Full/Disabled:**
        *   Locate the "Select location" combobox (it's a custom div/input, not a `<select>`).
        *   **Action:** Click the **text label** of the current selection (e.g., "FULL - Court 1") or the dropdown arrow to open the list.
        *   **Select:** Click a different option (e.g., "Court 2") from the `listbox` that appears.
        *   Verify "Book now" becomes enabled.
*   **Action:**
    *   Click "Book now" (`button:has-text("Book now")`).

## 3. Authentication (If not logged in)
*   **Redirect:** System shows a login form.
*   **Form Fields:**
    *   Email/ID: `input[type="text"]` (Label: "Email address or customer ID").
    *   Password: `input[type="password"]` (Label: "Password").
*   **Action:** Fill credentials and click "Log in".
*   **Post-Login:** System returns to the "Your selection" modal.
*   **Re-Verification:** Ensure the correct court is still selected (state might reset to default). Re-select if necessary.
*   **Action:** Click "Book now" again.

## 4. Checkout Process (`/basket/checkout`)
*   **State:** Checkout page with "Billing Details" and "Payment Method".
*   **Scenario A: Saved Card (Default)**
    *   **Detection:** "Pay with saved card" radio is checked.
    *   **Required Field:** "Security Code (CVV)" (`input[aria-label="Security Code (CVV)"]`).
*   **Scenario B: New Card / Different Card**
    *   **Action:** Select "Pay with a different card" radio.
    *   **Form Fields (Billing - Main Frame):**
        *   First Name: `input[aria-label="First name"]` or by placeholder.
        *   Last Name: `input[aria-label="Last name"]`.
        *   Address Line 1: `input[aria-label="Address line 1"]`.
        *   Town/City: `input[aria-label="Town/city"]`.
        *   Postcode: `input[aria-label="Postcode"]`.
    *   **Form Fields (Card - Opayo Iframe):**
        *   **Context:** Switch to iframe (`src*="opayo"`).
        *   Name: `input[name="cardholderName"]`.
        *   Card Number: `input[name="cardNumber"]`.
        *   Expiry (MMYY): `input[name="expiryDate"]`.
        *   CVC: `input[name="securityCode"]`.
*   **Final Action:**
    *   Ensure "Terms and Conditions" checkbox is checked.
    *   **Validation:** The "Pay now" button enables immediately upon valid input.
    *   Click "Pay now" (`button:has-text("Pay now")`).
    *   **Processing:** The button disables itself while processing. Do not navigate away.

## 5. Confirmation
*   **Success Page:** URL contains `/booking-confirmed/{reference_number}`.
*   **Indicators:**
    *   Heading: "Checkout successful".
    *   Reference number visible in URL or text.
