# Booking Process Analysis

This document outlines the step-by-step process for automating bookings on `bookings.better.org.uk`, based on manual investigation using the headless browser.

## 1. Availability Search
**URL Pattern:** `https://bookings.better.org.uk/location/{slug}/badminton-{duration}/{YYYY-MM-DD}/by-time`

*   **Page Load:**
    *   Accept Cookies: Click "Accept All Cookies" button (Selector: `button:has-text("Accept All Cookies")`).
    *   Check for "No results" message (Selector: text="No results were found at this centre").
*   **Slot Detection:**
    *   Available slots appear as links or interactive elements.
    *   Example Selector: `a[href*="/slot/"]` or detection of time text (e.g., "07:00 - 07:40").
*   **Action:** Click the slot element.

## 2. Slot Selection (Modal)
*   **State:** A modal or overlay appears with "Your selection".
*   **Action:**
    *   Check if "Book now" is enabled.
    *   If "Select location" (Court) is required, the system usually auto-selects the first available one (e.g., "Court 1").
    *   Click "Book now" (Selector: `button:has-text("Book now")`).

## 3. Authentication (If not logged in)
*   **Redirect:** System redirects to `/register` or shows a login form.
*   **Form Fields:**
    *   Email/ID: `input[type="text"]` (Label: "Email address or customer ID").
    *   Password: `input[type="password"]` (Label: "Password").
*   **Action:** Fill credentials and click "Log in".
*   **Post-Login:** System redirects back to the "Your selection" modal.
*   **Action:** Click "Book now" again.

## 4. Checkout Process (`/basket/checkout`)
*   **State:** Checkout page with "Payment Method" section.
*   **Scenario A: Saved Card (Default)**
    *   **Detection:** "Pay with saved card" radio is checked.
    *   **Required Field:** "Security Code (CVV)" (`input[aria-label="Security Code (CVV)"]` or similar).
    *   **Action:** Enter CVV (e.g., "063").
*   **Scenario B: New Card / Different Card**
    *   **Action:** Select "Pay with a different card" radio.
    *   **Form Fields (Billing - Main Frame):**
        *   First Name: `input[name="billing_first_name"]` (or similar)
        *   Last Name: `input[name="billing_last_name"]`
        *   Address Line 1: `input[name="billing_address_1"]`
        *   Town/City: `input[name="billing_city"]`
        *   Postcode: `input[name="billing_postcode"]`
    *   **Form Fields (Card - Opayo Iframe):**
        *   The card details are hosted in an Opayo iframe (`src*="opayo"`).
        *   **Context:** You must switch to the iframe context to interact with these fields.
        *   Cardholder Name: `input[name="cardholderName"]`
        *   Card Number: `input[name="cardNumber"]`
        *   Expiry (MMYY): `input[name="expiryDate"]`
        *   CVC: `input[name="securityCode"]`
    *   **Validation:** Ensure to trigger `blur` events or click outside after filling to ensure validation scripts run.
*   **Final Action:**
    *   Ensure "Terms and Conditions" checkbox is checked.
    *   Click "Pay now" (Selector: `button:has-text("Pay now")`).

## 5. Confirmation
*   **Success:** Wait for a confirmation page showing a "Reference Number".
*   **Validation:** Take a screenshot and extract the reference number.
