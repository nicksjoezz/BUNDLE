from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            page.goto("http://127.0.0.1:5000", timeout=60000)
            time.sleep(5)

            # Check Launch tab
            page.click("text=LAUNCH")
            time.sleep(2)
            page.screenshot(path="final_launch_check.png")

            # Check Operations tab
            page.click("text=OPERATIONS")
            time.sleep(2)
            page.screenshot(path="final_ops_check.png")

            # Check History tab
            page.click("text=HISTORY")
            time.sleep(2)
            page.screenshot(path="final_history_check.png")

            print("Verification screenshots saved.")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
