import os
import time
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError
from main import db, tasks, users, payments, bookings, logs, Task, TaskStatus, LogLevel, encrypt_value, decrypt_value, SystemLog, Booking

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BookingBot")

class BookingBot:
    def __init__(self, headless=True):
        self.headless = headless

    def log(self, level, message, task_id=None):
        print(f"[{level}] {message}")
        try:
            logs.insert(SystemLog(level=level, source="BookingBot", message=message, task_id=task_id))
        except Exception as e:
            print(f"Failed to write log to DB: {e}")

    def run_task(self, task: Task):
        self.log(LogLevel.INFO, f"Starting task {task.id} for {task.leisure_centre} on {task.target_date}", task.id)
        
        # 1. Fetch User & Payment
        try:
            user = users[task.user_account_id]
            payment = payments[task.payment_profile_id]
        except Exception as e:
            self.log(LogLevel.ERROR, f"Failed to fetch user/payment for task {task.id}: {e}", task.id)
            self.update_task_status(task, TaskStatus.FAILED)
            return

        # 2. Construct URL
        # Format: .../badminton-{duration}/{YYYY-MM-DD}/by-time
        duration_slug = f"badminton-{task.duration}min"
        url = f"https://bookings.better.org.uk/location/{task.leisure_centre}/{duration_slug}/{task.target_date}/by-time"
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context()
            page = context.new_page()
            
            try:
                # 3. Check Availability
                self.log(LogLevel.INFO, f"Checking URL: {url}", task.id)
                page.goto(url)
                
                # Cookie Consent
                try:
                    page.get_by_role("button", name="Accept All Cookies").click(timeout=5000)
                except:
                    pass 

                # Check for "No results"
                if page.get_by_text("No results were found at this centre").is_visible():
                    self.log(LogLevel.INFO, "No slots found.", task.id)
                    self.update_task_last_checked(task)
                    return 

                # Find Slots
                try:
                    page.wait_for_selector("a[href*='/slot/']", timeout=10000)
                except TimeoutError:
                    self.log(LogLevel.INFO, "Timeout waiting for slots (or none visible).", task.id)
                    self.update_task_last_checked(task)
                    return

                # Get all slots
                slots = page.locator("a[href*='/slot/']").all()
                if not slots:
                    self.log(LogLevel.INFO, "No booking slots found.", task.id)
                    self.update_task_last_checked(task)
                    return
                
                # 4. Filter Slots based on Preference
                target_slot = None
                
                if task.target_time_start:
                    self.log(LogLevel.INFO, f"Looking for slot starting at {task.target_time_start}...", task.id)
                    # Iterate and check URL or text for time
                    # URL format: .../slot/07:00-07:40/...
                    target_time_str = f"/slot/{task.target_time_start}"
                    
                    for s in slots:
                        href = s.get_attribute("href")
                        if href and target_time_str in href:
                            target_slot = s
                            break
                    
                    if not target_slot:
                        self.log(LogLevel.INFO, f"No slot found matching time {task.target_time_start}.", task.id)
                        self.update_task_last_checked(task)
                        return
                else:
                    # Pick first available
                    target_slot = slots[0]

                # Attempt Booking
                self.log(LogLevel.INFO, "Clicking slot...", task.id)
                target_slot.click()
                
                # 5. "Your Selection" Modal
                try:
                    page.get_by_role("button", name="Book now").click()
                except TimeoutError:
                    self.log(LogLevel.ERROR, "Could not click 'Book now' (maybe disabled/court selection needed?)", task.id)
                    return

                # 6. Login (If redirected)
                if page.get_by_label("Email address or customer ID").is_visible():
                    self.log(LogLevel.INFO, "Logging in...", task.id)
                    page.get_by_label("Email address or customer ID").fill(user.email)
                    
                    pwd = decrypt_value(user.password_encrypted)
                    page.get_by_label("Password", exact=True).fill(pwd)
                    
                    page.get_by_role("button", name="Log in").click()
                    
                    try:
                        page.get_by_role("button", name="Book now").click(timeout=10000)
                    except:
                        pass 

                # 7. Checkout / Basket
                try:
                    page.wait_for_url("**/checkout", timeout=15000)
                except:
                    self.log(LogLevel.ERROR, "Failed to reach checkout page.", task.id)
                    return

                self.log(LogLevel.INFO, "At Checkout. Filling billing details...", task.id)
                
                # 8. Fill Billing Details
                page.get_by_label("Pay with a different card").check()
                
                try:
                    page.get_by_label("First name").fill(user.name.split()[0]) 
                    page.get_by_label("Last name").fill(user.name.split()[-1] if len(user.name.split()) > 1 else "User")
                    page.get_by_label("Address line 1").fill(payment.address_line_1)
                    page.get_by_label("Town/city").fill(payment.city)
                    page.get_by_label("Postcode").fill(payment.postcode)
                except Exception as e:
                    self.log(LogLevel.WARN, f"Error filling billing address: {e}", task.id)

                # 9. Opayo Iframe (Card Details)
                self.log(LogLevel.INFO, "Filling Card Details...", task.id)
                
                page.wait_for_selector("iframe[src*='opayo']", timeout=10000)
                frame = None
                for f in page.frames:
                    if "opayo" in f.url:
                        frame = f
                        break
                
                if not frame:
                    self.log(LogLevel.ERROR, "Could not find Payment Iframe.", task.id)
                    return

                try:
                    frame.get_by_label("Name").fill(payment.cardholder_name)
                    cn = decrypt_value(payment.card_number_encrypted)
                    frame.get_by_label("Card").fill(cn)
                    exp = f"{payment.expiry_month}{payment.expiry_year}"
                    frame.get_by_label("Expiry").fill(exp)
                    cvv = decrypt_value(payment.cvv_encrypted)
                    frame.get_by_label("CVC").fill(cvv)
                except Exception as e:
                    self.log(LogLevel.ERROR, f"Error filling Iframe: {e}", task.id)
                    return

                # 10. Finalize
                self.log(LogLevel.INFO, "Finalizing...", task.id)
                page.get_by_label("I agree to the Terms and Conditions").check()
                
                pay_btn = page.get_by_role("button", name="Pay now")
                
                if pay_btn.is_disabled():
                    page.mouse.click(0, 0)
                    time.sleep(1)
                
                if pay_btn.is_disabled():
                    self.log(LogLevel.ERROR, "Pay Now button is still disabled after filling.", task.id)
                    return

                pay_btn.click()
                
                # 11. Confirmation
                try:
                    page.wait_for_url("**/confirmation", timeout=30000)
                    ref = "CONFIRMED" 
                    
                    bookings.insert(Booking(
                        task_id=task.id,
                        reference_number=ref,
                        court_name="Auto-Assigned",
                        price="Unknown"
                    ))
                    
                    self.update_task_status(task, TaskStatus.SUCCESS)
                    self.log(LogLevel.INFO, "Booking Successful!", task.id)
                    
                except TimeoutError:
                    self.log(LogLevel.ERROR, "Timeout waiting for confirmation.", task.id)
            
            except Exception as e:
                self.log(LogLevel.ERROR, f"Unexpected error in bot run: {e}", task.id)

    def update_task_status(self, task, status):
        task.status = status.value
        tasks.update(task)

    def update_task_last_checked(self, task):
        task.last_checked_at = datetime.now()
        tasks.update(task)

def run_worker():
    bot = BookingBot(headless=True)
    print("Worker started. Polling for tasks...")
    while True:
        try:
            pending_tasks = tasks(where="status IN ('PENDING', 'RUNNING')")
            for t in pending_tasks:
                should_run = False
                if t.status == TaskStatus.PENDING.value:
                    should_run = True
                elif t.status == TaskStatus.RUNNING.value:
                    last_check = t.last_checked_at
                    if isinstance(last_check, str):
                        try:
                            last_check = datetime.fromisoformat(last_check)
                        except:
                            last_check = None

                    if last_check and (datetime.now() - last_check).total_seconds() > 300:
                        should_run = True
                    elif not last_check:
                        should_run = True
                
                if should_run:
                    if t.status == TaskStatus.PENDING.value:
                        bot.update_task_status(t, TaskStatus.RUNNING)
                    
                    bot.run_task(t)
            
            time.sleep(10)
            
        except Exception as e:
            print(f"Worker Loop Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_worker()