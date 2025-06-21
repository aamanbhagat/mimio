import asyncio
import random
import time
import re
import string # For generating random session suffixes
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Locator

# --- Configuration ---
URL_FILE_PATH = "/teamspace/studios/this_studio/scaling-computing-machine/sorry.txt"
PROXY_SERVER = "http://brd.superproxy.io:33335"
PROXY_USERNAME_BASE = "brd-customer-hl_c19cf957-zone-datacenter_proxy1" # Base username
PROXY_PASSWORD = "f650jr89f4oq"

# Set to True to append a random session suffix to the proxy username (e.g., username-session-randomstr)
# This MAY help with IP rotation if your BrightData zone supports it.
# If not, or if it causes issues, set to False. IP rotation will then solely depend on your zone's config.
USE_DYNAMIC_PROXY_USERNAME_SUFFIX = True

# --- Helper Functions ---

def get_random_url(filepath: str) -> str | None:
    """Reads all lines from a file and returns a random line (URL)."""
    # This function is called by each instance, so file access needs to be safe.
    # For simplicity, keeping it as is. For very high concurrency, consider pre-loading URLs.
    # print(f"[{time.strftime('%H:%M:%S')}] Reading URLs from: {filepath}") # Can be noisy with many instances
    try:
        with open(filepath, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        if not urls:
            # print(f"[{time.strftime('%H:%M:%S')}] No URLs found in {filepath}.") # Can be noisy
            return None
        selected_url = random.choice(urls)
        # print(f"[{time.strftime('%H:%M:%S')}] Selected URL: {selected_url}") # Can be noisy
        return selected_url
    except FileNotFoundError:
        # print(f"[{time.strftime('%H:%M:%S')}] Error: URL file not found at {filepath}") # Can be noisy
        return None
    except Exception as e:
        # print(f"[{time.strftime('%H:%M:%S')}] Error reading URL file {filepath}: {e}") # Can be noisy
        return None

async def click_element_with_retry(
    page,
    locator_strategies: list,
    description: str,
    instance_id: int, # Added for logging
    action_timeout_ms: int = 60000,
    js_click: bool = True
) -> bool:
    """
    Attempts to find and click an element using multiple strategies with retries.
    """
    log_prefix = f"[{time.strftime('%H:%M:%S')}] Instance {instance_id}:"
    print(f"{log_prefix} Attempting action: {description}")
    overall_deadline = time.time() + action_timeout_ms / 1000.0

    while time.time() < overall_deadline:
        for i, strategy_item in enumerate(locator_strategies):
            element_locator = None
            strategy_description = ""
            try:
                if isinstance(strategy_item, str):
                    element_locator = page.locator(strategy_item)
                    strategy_description = f"CSS selector '{strategy_item}'"
                elif callable(strategy_item):
                    element_locator = strategy_item(page)
                    strategy_description = f"custom function strategy {i+1}"
                elif isinstance(strategy_item, Locator):
                    element_locator = strategy_item
                    strategy_description = f"pre-defined Locator object {i+1}"
                else:
                    print(f"{log_prefix}   Unsupported locator strategy type for '{description}'. Skipping.")
                    continue
                
                # print(f"{log_prefix}   Trying strategy for '{description}': {strategy_description}") # Can be very verbose
                target_element = element_locator.first

                await target_element.wait_for(state="visible", timeout=3000)
                
                # print(f"{log_prefix}   Element for '{description}' found and visible with {strategy_description}. Attempting click.") # Verbose
                if js_click:
                    await target_element.evaluate("el => el.click()")
                else:
                    await target_element.click(timeout=5000)
                
                print(f"{log_prefix} Successfully clicked: {description} using {strategy_description}")
                await asyncio.sleep(0.5) # Using asyncio.sleep
                return True
            
            except PlaywrightTimeoutError as pte:
                # print(f"{log_prefix}   Strategy {strategy_description} for '{description}' timed out: {str(pte).splitlines()[0]}") # Less verbose timeout log
                pass
            except Exception as e:
                print(f"{log_prefix}   Error with strategy {strategy_description} for '{description}': {type(e).__name__} - {e}")

        await asyncio.sleep(0.2)

    print(f"{log_prefix} FAILED: Could not click '{description}' after {action_timeout_ms/1000}s.")
    return False

async def run_automation_on_page(page, instance_id: int): # Added instance_id
    """Performs the sequence of actions on the given page."""
    log_prefix = f"[{time.strftime('%H:%M:%S')}] Instance {instance_id}:"
    actions = [
        {
            "description": "1. I Am Not Robot button",
            "locators": [
                "button.rtg_btn#robot",
                lambda p: p.get_by_role('button', name='I Am Not Robot'),
                lambda p: p.locator('//button[@id="robot" and contains(text(), "I Am Not Robot")]')
            ],
            "causes_navigation": False, "pre_wait_ms": 0,
            "post_success_wait_ms": 2500 
        },
        {
            "description": "2. Dual Tap \"Go Link\" button",
            "locators": [
                "button#rtgli1[onclick*='scrol']", 
                lambda p: p.locator('//button[@id="rtgli1" and contains(normalize-space(.), \'Dual Tap "Go Link"\')]'),
                lambda p: p.get_by_role('button', name=re.compile(r'Dual Tap "Go Link"', re.IGNORECASE)).filter(has_selector="#rtgli1"),
                "//button[@id='rtgli1']"
            ],
            "causes_navigation": False, "pre_wait_ms": 0
        },
        # ... (all other actions remain the same as your last provided list) ...
        {
            "description": "3. Dual Tap \"Continue\" button",
            "locators": [
                "button#robot2[onclick*='rtglink']", 
                lambda p: p.get_by_role('button', name='Dual Tap "Continue"').filter(has_selector="#robot2"),
                lambda p: p.locator('//button[@id="robot2" and contains(normalize-space(.), \'Dual Tap "Continue"\')]')
            ],
            "causes_navigation": False, "pre_wait_ms": 0
        },
        {
            "description": "4. GO TO LINK - CLICK OPEN button",
            "locators": [
                "button#rtg-snp2.rtg_btn[type='submit']", 
                lambda p: p.get_by_role('button', name='GO TO LINK - CLICK OPEN').filter(has_selector="#rtg-snp2"),
                lambda p: p.locator('//button[@id="rtg-snp2" and contains(normalize-space(.), "GO TO LINK - CLICK OPEN")]')
            ],
            "causes_navigation": True, "pre_wait_ms": 0
        },
        {
            "description": "5. Click to proceed image",
            "locators": [
                "img[alt='Click to proceed'][src*='KvyIEsF.png']", 
                lambda p: p.get_by_alt_text('Click to proceed'),
                lambda p: p.locator('//img[@alt="Click to proceed" and contains(@src, "KvyIEsF.png")]')
            ],
            "causes_navigation": True, "pre_wait_ms": 0
        },
        {
            "description": "6. Continue button (blue)",
            "locators": [
                "button#btn7.ce-btn.ce-blue:has-text('Continue')", 
                lambda p: p.get_by_role('button', name='Continue').filter(has_selector="#btn7.ce-blue"),
                lambda p: p.locator('//button[@id="btn7" and contains(@class, "ce-blue") and normalize-space(.)="Continue"]')
            ],
            "causes_navigation": True, "pre_wait_ms": 0
        },
        {
            "description": "7. Close button (generic)",
            "locators": [
                "button.close-btn", "button[class*='close']", "button[aria-label*='Close'], button[aria-label*='close']",
                lambda p: p.get_by_role('button', name=re.compile(r'close|×', re.IGNORECASE)),
                lambda p: p.locator('//button[contains(@class, "close-btn") or contains(@aria-label, "Close") or contains(@aria-label, "close") or text()="×"]')
            ],
            "causes_navigation": False, "pre_wait_ms": 0
        },
        {   "description": "8. Top button (ID only)", "locators": ["button#topButton"], "causes_navigation": False, "pre_wait_ms": 0 },
        {
            "description": "9. Top Continue button",
            "locators": [
                "button#topButton.pro_btn:has-text('Continue')",
                lambda p: p.locator("#topButton.pro_btn").filter(has_text="Continue"),
                lambda p: p.get_by_role('button', name='Continue').filter(has_selector="#topButton.pro_btn")
            ],
            "causes_navigation": False, "pre_wait_ms": 0
        },
        {
            "description": "10. Bottom Click To Continue button",
            "locators": [
                "button#bottomButton.pro_btn:has-text('Click To Continue')",
                 lambda p: p.locator("#bottomButton.pro_btn").filter(has_text="Click To Continue"),
                 lambda p: p.get_by_role('button', name='Click To Continue').filter(has_selector="#bottomButton.pro_btn")
            ],
            "causes_navigation": False, "pre_wait_ms": 0
        },
        {
            "description": "11. Bottom Next button",
            "locators": [
                "button#bottomButton.pro_btn:has-text('Next')",
                lambda p: p.locator("#bottomButton.pro_btn").filter(has_text="Next"),
                lambda p: p.get_by_role('button', name='Next').filter(has_selector="#bottomButton.pro_btn")
            ],
            "causes_navigation": True, "pre_wait_ms": 0
        },
        {
            "description": "12. Success link (a.btn-success)",
            "locators": [
                "a.btn-success",
                lambda p: p.get_by_role('link').filter(has_selector="a.btn-success"),
                lambda p: p.locator('//a[contains(@class, "btn-success") and (normalize-space(.) or contains(text(), "Get") or contains(text(), "Download"))]')
            ],
            "causes_navigation": False, "pre_wait_ms": 6000
        }
    ]

    for action_item in actions:
        if action_item["pre_wait_ms"] > 0:
            print(f"{log_prefix} Waiting for {action_item['pre_wait_ms']}ms before action: {action_item['description']}")
            await asyncio.sleep(action_item["pre_wait_ms"] / 1000.0)

        if await click_element_with_retry(page, action_item["locators"], action_item["description"], instance_id):
            if action_item.get("post_success_wait_ms", 0) > 0:
                print(f"{log_prefix} Post-success wait: {action_item['post_success_wait_ms']}ms for '{action_item['description']}'")
                await asyncio.sleep(action_item["post_success_wait_ms"] / 1000.0)

            if action_item["causes_navigation"]:
                print(f"{log_prefix} Action '{action_item['description']}' might cause navigation. Waiting for page to settle...")
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=30000) 
                    print(f"{log_prefix} Navigation/load detected or timeout. New URL: {page.url}")
                except PlaywrightTimeoutError:
                    print(f"{log_prefix} Timeout waiting for navigation/load after '{action_item['description']}'. Current URL: {page.url}. Proceeding.")
                except Exception as e:
                    print(f"{log_prefix} Error during post-click wait for '{action_item['description']}': {e}. Current URL: {page.url}. Proceeding.")
        else: 
            print(f"{log_prefix} Critical step failed: {action_item['description']}. Ending automation for this URL.")
            raise Exception(f"Instance {instance_id} failed at: {action_item['description']}") # Raise error to trigger restart

    print(f"{log_prefix} All actions attempted successfully for {page.url}.")


async def instance_workflow(instance_id: int, playwright_manager):
    """Manages the lifecycle of a single browser instance, looping infinitely."""
    log_prefix = f"[{time.strftime('%H:%M:%S')}] Instance {instance_id}:"
    print(f"{log_prefix} Initializing.")

    while True: # Infinite loop for this instance
        target_url = get_random_url(URL_FILE_PATH)
        if not target_url:
            print(f"{log_prefix} No URL found or error reading URL file. Retrying in 30s...")
            await asyncio.sleep(30)
            continue

        print(f"{log_prefix} Starting automation for URL: {target_url}")
        
        browser = None
        context = None
        page_object = None # To ensure page is closable in finally if it was created

        current_proxy_username = PROXY_USERNAME_BASE
        if USE_DYNAMIC_PROXY_USERNAME_SUFFIX:
            session_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            current_proxy_username = f"{PROXY_USERNAME_BASE}-session-{session_suffix}"
        
        try:
            print(f"{log_prefix} Launching browser with proxy user: {current_proxy_username}")
            browser = await playwright_manager.chromium.launch(
                headless=True, 
                proxy={
                    "server": PROXY_SERVER,
                    "username": current_proxy_username,
                    "password": PROXY_PASSWORD,
                },
                args=[
                    '--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas', '--no-zygote', '--disable-gpu',
                    '--window-size=1280,720' # Define a window size
                ]
            )
            
            context = await browser.new_context(
                ignore_https_errors=True, 
                user_agent=f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/10{random.randint(0,2)}.0.{random.randint(4000,5000)}.{random.randint(100,200)} Safari/537.36 Instance/{instance_id}",
                java_script_enabled=True,
                accept_downloads=False, # Usually not needed for this kind of task
                # viewport={'width': 1280, 'height': 720} # Set viewport
            )
            page_object = await context.new_page()
            
            print(f"{log_prefix} Navigating to: {target_url}")
            initial_load_timeout_ms = 60000
            try:
                await page_object.goto(target_url, timeout=initial_load_timeout_ms, wait_until="domcontentloaded")
                print(f"{log_prefix} Initial page navigation successful or timeout. URL: {page_object.url}")
            except PlaywrightTimeoutError:
                print(f"{log_prefix} Initial page load for {target_url} timed out after {initial_load_timeout_ms/1000}s. Proceeding...")
            except Exception as e_goto: # Catch specific goto errors
                print(f"{log_prefix} Critical error during initial page load for {target_url}: {type(e_goto).__name__} - {e_goto}. Aborting this attempt.")
                raise # Re-raise to trigger cleanup and restart of instance

            await run_automation_on_page(page_object, instance_id)

            print(f"{log_prefix} Automation sequence finished for {target_url}. Waiting 2s before next cycle.")
            await asyncio.sleep(2)

        except Exception as e:
            print(f"{log_prefix} ERROR during automation for {target_url}: {type(e).__name__} - {e}. Instance will restart.")
            # Error is caught, instance will loop and restart.
        finally:
            print(f"{log_prefix} Cleaning up resources for URL: {target_url}...")
            if page_object:
                try: await page_object.close()
                except Exception as e_page_close: print(f"{log_prefix} Error closing page: {e_page_close}")
            if context:
                try: await context.close()
                except Exception as e_context_close: print(f"{log_prefix} Error closing context: {e_context_close}")
            if browser:
                try: await browser.close()
                except Exception as e_browser_close: print(f"{log_prefix} Error closing browser: {e_browser_close}")
            
            print(f"{log_prefix} Resources cleaned. Restarting loop for instance.")
            # Small delay before the instance fully restarts its loop to prevent rapid hammering on persistent issues
            await asyncio.sleep(random.randint(5, 10)) 

async def main():
    """Main function to ask for number of instances and run them concurrently."""
    try:
        num_instances_str = input("Enter the number of concurrent instances to run: ")
        num_instances = int(num_instances_str)
        if num_instances <= 0:
            print("Number of instances must be a positive integer.")
            return
    except ValueError:
        print("Invalid input. Please enter a whole number.")
        return

    print(f"[{time.strftime('%H:%M:%S')}] Starting {num_instances} concurrent instance(s)...")
    print(f"[{time.strftime('%H:%M:%S')}] Using dynamic proxy username suffix: {USE_DYNAMIC_PROXY_USERNAME_SUFFIX}")
    print(f"[{time.strftime('%H:%M:%S')}] NOTE: Effective IP rotation depends on your BrightData proxy zone configuration.")
    
    async with async_playwright() as playwright_manager:
        tasks = []
        for i in range(num_instances):
            tasks.append(asyncio.create_task(instance_workflow(i + 1, playwright_manager)))
        
        try:
            await asyncio.gather(*tasks) # This will run "forever" as tasks loop infinitely
        except Exception as e:
            # This part should ideally not be reached if instance_workflow handles its errors
            print(f"[{time.strftime('%H:%M:%S')}] A critical error occurred in the main task manager: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n[{time.strftime('%H:%M:%S')}] Program interrupted by user. Exiting.")
    except Exception as e_global:
        print(f"\n[{time.strftime('%H:%M:%S')}] A global unhandled error occurred: {e_global}")
