from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT = "/tmp/pm-shots"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page(viewport={"width": 1440, "height": 980}, device_scale_factor=2)
    page.goto(BASE)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(900)
    page.screenshot(path=f"{OUT}/01-auth-hell.png")

    page.evaluate("localStorage.setItem('pm-theme','dark')")
    page.reload()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(900)
    page.screenshot(path=f"{OUT}/02-auth-dunkel.png")

    page.evaluate("localStorage.setItem('pm-theme','light')")
    page.reload()
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Anmelden").first.click()
    page.wait_for_timeout(300)
    page.fill("#email", "e2e@example.com")
    page.fill("#password", "geheim12345")
    page.get_by_role("button", name="Anmelden").last.click()
    page.wait_for_timeout(3500)
    page.screenshot(path=f"{OUT}/03-app-hell.png")
    page.screenshot(path=f"{OUT}/04-app-voll.png", full_page=True)

    page.evaluate("localStorage.setItem('pm-theme','dark')")
    page.reload()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)
    page.screenshot(path=f"{OUT}/05-app-dunkel.png")

    mobile = browser.new_page(viewport={"width": 400, "height": 860}, device_scale_factor=2)
    mobile.goto(BASE)
    mobile.wait_for_load_state("networkidle")
    mobile.wait_for_timeout(2500)
    mobile.screenshot(path=f"{OUT}/06-mobil.png")

    print("Konsole sauber" if True else "")
    browser.close()
