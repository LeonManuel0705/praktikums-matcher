from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page(viewport={"width": 900, "height": 1000}, device_scale_factor=2)
    page.goto("http://127.0.0.1:8001")
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Anmelden").first.click()
    page.fill("#email", "klick@example.com")
    page.fill("#password", "geheim12345")
    page.get_by_role("button", name="Anmelden").last.click()
    page.wait_for_selector("text=Suchtiefe", timeout=15000)
    page.get_by_role("button", name="sparsam").scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    box = page.locator(".rail .panel").bounding_box()
    page.screenshot(path="/tmp/pm-shots/09-tiefe.png",
                    clip={"x": box["x"], "y": max(0, box["y"] + box["height"] - 430),
                          "width": box["width"], "height": 430})
    for name in ("sparsam", "normal", "gründlich"):
        page.get_by_role("button", name=name, exact=True).click()
        page.wait_for_timeout(200)
        print(f"  {name:11} -> {page.locator('.slider-value').last.inner_text()}")
    b.close()
