import os
import time
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError
from playwright_stealth import Stealth
from main import db, tasks, users, payments, bookings, logs, Task, TaskStatus, LogLevel, encrypt_value, decrypt_value, SystemLog, Booking

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BookingBot")

class BookingBot:
    def __init__(self, headless=True):
        self.headless = headless
        os.makedirs("/app/screenshots", exist_ok=True)
        os.makedirs("/app/videos", exist_ok=True)

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
        duration_slug = f"badminton-{task.duration}min"
        url = f"https://bookings.better.org.uk/location/{task.leisure_centre}/{duration_slug}/{task.target_date}/by-time"
        
        with sync_playwright() as p:
            # Use realistic User Agent to avoid blocking
            browser = p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                record_video_dir="/app/videos/",
                record_video_size={"width": 1280, "height": 1440},
                viewport={"width": 1280, "height": 1440}
            )
            page = context.new_page()
            Stealth().apply_stealth_sync(page)

            try:
                # 3. Check Availability
                self.log(LogLevel.INFO, f"Checking URL: {url}", task.id)
                page.goto(url)
                
                try: page.screenshot(path=f"/app/screenshots/step0_page_load_{task.id}.png", full_page=True)
                except Exception as e: self.log(LogLevel.ERROR, f"Screenshot 0 failed: {e}", task.id)
                
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

                # 4. Pre-emptive Login
                # Check for main "Log in" button (header)
                # Use test_id to avoid matching other login buttons (e.g. empty basket)
                login_btn = page.get_by_test_id("login")
                if login_btn.is_visible():
                    self.log(LogLevel.INFO, "Performing pre-emptive login...", task.id)
                    try:
                        login_btn.click()
                        # Wait for login form
                        page.wait_for_selector("input[id='password']", timeout=10000)
                        
                        page.get_by_label("Email address or customer ID").fill(user.email)
                        pwd = decrypt_value(user.password_encrypted)
                        page.get_by_label("Password", exact=True).fill(pwd)
                        page.get_by_role("button", name="Log in").click()
                        
                        # Wait for redirect back
                        page.wait_for_url(url, timeout=30000)
                        self.log(LogLevel.INFO, "Login successful, returned to availability page.", task.id)
                        try: page.screenshot(path=f"/app/screenshots/step1_login_success_{task.id}.png", full_page=True)
                        except Exception as e: self.log(LogLevel.ERROR, f"Screenshot 1 failed: {e}", task.id)
                    except Exception as e:
                        try: page.screenshot(path=f"/app/screenshots/step1_login_failed_{task.id}.png", full_page=True)
                        except Exception as e: self.log(LogLevel.ERROR, f"Screenshot 1 failed: {e}", task.id)

                        self.log(LogLevel.WARN, f"Pre-emptive login failed: {e}", task.id)

                # 5. Find Slots
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
                    
                    try: page.screenshot(path=f"/app/screenshots/step2_slots_not_found_{task.id}.png", full_page=True)
                    except Exception as e: self.log(LogLevel.ERROR, f"Screenshot 2 failed: {e}", task.id)
                    
                    self.update_task_last_checked(task)
                    return
                
                try: page.screenshot(path=f"/app/screenshots/step2_slots_found_{task.id}.png", full_page=True)
                except Exception as e: self.log(LogLevel.ERROR, f"Screenshot 2 failed: {e}", task.id)
                
                # Filter Slots based on Preference
                target_slot = None
                if task.target_time_start:
                    self.log(LogLevel.INFO, f"Looking for slot starting at {task.target_time_start}...", task.id)
                    target_time_str = f"/slot/{task.target_time_start}"
                    for s in slots:
                        href = s.get_attribute("href")
                        if href and target_time_str in href:
                            target_slot = s
                            break
                    if not target_slot:
                        self.log(LogLevel.INFO, f"No slot found matching time {task.target_time_start}.", task.id)
                        
                        try: page.screenshot(path=f"/app/screenshots/step2_slots_not_found_{task.id}.png", full_page=True)
                        except Exception as e: self.log(LogLevel.ERROR, f"Screenshot 2 failed: {e}", task.id)
                        
                        self.update_task_last_checked(task)
                        return
                else:
                    target_slot = slots[0]

                # Click Slot
                self.log(LogLevel.INFO, "Clicking slot...", task.id)
                target_slot.click()
                
                # 6. "Your Selection" Modal & Booking
                try:
                    # Court Selection Logic
                    book_btn = page.get_by_role("button", name="Book now")
                    
                    # Logic to switch court if full/disabled
                    def handle_full_court():
                        # Wait a moment for button state to settle
                        time.sleep(1)
                        if book_btn.is_disabled() or page.get_by_text("The session being booked is already full").is_visible():
                            self.log(LogLevel.INFO, "Default court full. Attempting to switch...", task.id)
                            # Find "FULL" text to click
                            full_text = page.get_by_text("FULL -", exact=False).first
                            if full_text.is_visible():
                                full_text.click()
                                try:
                                    # Select the last option
                                    page.get_by_role("listbox").get_by_role("option").last.click()
                                    self.log(LogLevel.INFO, "Switched court.", task.id)
                                    try: page.screenshot(path=f"/app/screenshots/step2_handling_full_court_{task.id}.png", full_page=True)
                                    except Exception as e: self.log(LogLevel.ERROR, f"Screenshot switch failed: {e}", task.id)
                                    time.sleep(1)
                                except:
                                    self.log(LogLevel.ERROR, "Failed to select alternative court.", task.id)

                    handle_full_court()
                    book_btn.click()
                except TimeoutError:
                    self.log(LogLevel.ERROR, "Could not click 'Book now' (maybe disabled/court selection needed?)", task.id)
                    return

                # 7. Login Fallback (If pre-emptive failed)
                if page.get_by_label("Email address or customer ID").is_visible():
                    self.log(LogLevel.INFO, "Logging in (fallback)...", task.id)
                    page.get_by_label("Email address or customer ID").fill(user.email)
                    pwd = decrypt_value(user.password_encrypted)
                    page.get_by_label("Password", exact=True).fill(pwd)
                    page.get_by_role("button", name="Log in").click()
                    
                    try:
                        # Re-check after login
                        book_btn = page.get_by_role("button", name="Book now")
                        try: page.screenshot(path=f"/app/screenshots/step1_login_fallback_success_{task.id}.png", full_page=True)
                        except: pass

                        handle_full_court()
                        book_btn.click(timeout=10000)
                    except:
                        pass 

                # 8. Checkout / Basket
                try:
                    page.wait_for_url("**/checkout", timeout=15000)
                except:
                    self.log(LogLevel.ERROR, "Failed to reach checkout page.", task.id)
                    return

                self.log(LogLevel.INFO, "At Checkout. Filling billing details...", task.id)
                
                # 9. Fill Billing Details
                try:
                    # Robustly check 'Pay with a different card'
                    saved_card = page.get_by_label("Pay with saved card")
                    if saved_card.is_visible() and saved_card.is_checked():
                        page.get_by_label("Pay with a different card").check()
                    elif not saved_card.is_visible():
                        diff_card = page.get_by_label("Pay with a different card")
                        if diff_card.is_visible():
                            diff_card.check()
                except Exception as e:
                    self.log(LogLevel.ERROR, f"Error selecting payment method: {e}", task.id)
                    try: page.screenshot(path=f"/app/screenshots/error_checkout_{task.id}.png", full_page=True)
                    except: pass
                    return 
                
                try:
                    page.get_by_label("First name").fill(payment.cardholder_name.split()[0]) 
                    page.get_by_label("Last name").fill(payment.cardholder_name.split()[-1] if len(payment.cardholder_name.split()) > 1 else "")
                    
                    # Address Line 1 often lacks a proper label association
                    try:
                        page.get_by_label("Address line 1").fill(payment.address_line_1)
                    except:
                        # Fallback: Find input near text
                        page.locator("div").filter(has_text="Address line 1").last.locator("input").first.fill(payment.address_line_1)

                    page.get_by_label("Town/city").fill(payment.city)
                    page.get_by_label("Postcode").fill(payment.postcode)
                except Exception as e:
                    self.log(LogLevel.WARN, f"Error filling billing address: {e}", task.id)
                    try: page.screenshot(path=f"/app/screenshots/error_billing_{task.id}.png", full_page=True)
                    except: pass

                # 10. Opayo Iframe (Card Details)
                self.log(LogLevel.INFO, "Filling Card Details...", task.id)
                
                try:
                    # Wait for iframe element and get content frame
                    iframe_el = page.wait_for_selector("iframe[src*='opayo']", timeout=20000)
                    iframe_el.scroll_into_view_if_needed()
                    frame = iframe_el.content_frame()
                    if not frame:
                        # Sometimes content_frame is null if cross-origin isn't ready? 
                        # Try finding by url again as fallback
                        time.sleep(2)
                        for f in page.frames:
                            if "opayo" in f.url:
                                frame = f
                                break
                    
                    if not frame:
                        raise Exception("Could not find Opayo iframe content")

                    # Use placeholders as fallback if names fail
                    try:
                        frame.get_by_placeholder("Cardholder Name").press_sequentially(payment.cardholder_name, delay=100)
                    except:
                        frame.locator("input[name='cardholderName']").press_sequentially(payment.cardholder_name, delay=100)

                    cn = decrypt_value(payment.card_number_encrypted)
                    try:
                        frame.get_by_placeholder("0000 0000 0000 0000").press_sequentially(cn, delay=100)
                    except:
                         frame.locator("input[name='cardNumber']").press_sequentially(cn, delay=100)

                    exp = f"{payment.expiry_month}{payment.expiry_year}"
                    try:
                        frame.get_by_placeholder("MMYY").press_sequentially(exp, delay=100)
                    except:
                        frame.locator("input[name='expiryDate']").press_sequentially(exp, delay=100)

                    cvv = decrypt_value(payment.cvv_encrypted)
                    try:
                        frame.get_by_placeholder("123").press_sequentially(cvv, delay=100)
                    except:
                        frame.locator("input[name='securityCode']").press_sequentially(cvv, delay=100)
                        
                    try: page.screenshot(path=f"/app/screenshots/step3_details_filled_{task.id}.png", full_page=True)
                    except: pass

                except Exception as e:
                    self.log(LogLevel.ERROR, f"Error filling Iframe: {e}", task.id)
                    try: page.screenshot(path=f"/app/screenshots/error_iframe_{task.id}.png", full_page=True)
                    except: pass
                    return

                # 11. Finalize
                self.log(LogLevel.INFO, "Finalizing...", task.id)
                page.get_by_label("I agree to the Terms and Conditions").check()
                
                pay_btn = page.get_by_role("button", name="Pay now")
                
                if pay_btn.is_disabled():
                    page.mouse.click(0, 0)
                    time.sleep(1)
                
                if pay_btn.is_disabled():
                    self.log(LogLevel.ERROR, "Pay Now button is still disabled after filling.", task.id)
                    return

                time.sleep(1)
                try: page.screenshot(path=f"/app/screenshots/step4_before_pay_{task.id}.png", full_page=True)
                except: pass

                pay_btn.click()
                
                # 12. Confirmation
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
                    try: page.screenshot(path=f"/app/screenshots/step5_confirmation_{task.id}.png", full_page=True)
                    except: pass
                    
                except TimeoutError:
                    self.log(LogLevel.ERROR, "Timeout waiting for confirmation.", task.id)
                    try: page.screenshot(path=f"/app/screenshots/error_confirmation_timeout_{task.id}.png", full_page=True)
                    except Exception as e: self.log(LogLevel.ERROR, f"Screenshot confirmation timeout failed: {e}", task.id)
            
            except Exception as e:
                self.log(LogLevel.ERROR, f"Unexpected error in bot run: {e}", task.id)
            finally:
                try:
                    page.close()
                    context.close()
                    # Rename video
                    video_path = page.video.path()
                    if video_path:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        new_path = f"/app/videos/task_{task.id}_{timestamp}.webm"
                        os.rename(video_path, new_path)
                        self.log(LogLevel.INFO, f"Video saved to {new_path}", task.id)
                except Exception as e:
                    self.log(LogLevel.WARN, f"Failed to save video: {e}", task.id)

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
