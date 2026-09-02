from playwright.sync_api import expect, sync_playwright

BASE = "http://127.0.0.1:8001"
errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 980}, device_scale_factor=2)
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(BASE)
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="Konto anlegen").click()
    page.fill("#name", "Testschüler")
    page.fill("#email", "klick@example.com")
    page.fill("#password", "geheim12345")
    page.get_by_role("button", name="Konto anlegen").last.click()
    page.wait_for_selector("text=Wunsch-Profil", timeout=15000)
    print("1. Konto angelegt, App sichtbar")

    page.get_by_role("button", name="Wirtschaft").click()
    page.fill("#location", "Berlin")
    page.get_by_label("Umkreis in Kilometern").fill("40")
    page.get_by_label("Startdatum").fill("2027-03-01")
    page.get_by_label("Enddatum").fill("2027-03-26")
    page.get_by_role("button", name="bezahlt", exact=True).click()
    page.fill("#wishes", "möchte was mit Daten und Marketing machen")
    page.wait_for_timeout(700)
    print("2. Profil ausgefüllt")

    expect(page.get_by_role("button", name="Suche starten")).to_be_disabled()
    print("3. Suche ist gesperrt, solange nicht gespeichert")

    page.get_by_role("button", name="Profil speichern").click()
    page.wait_for_timeout(900)
    expect(page.get_by_role("button", name="Suche starten")).to_be_enabled()
    print("4. Nach dem Speichern ist die Suche freigegeben")

    page.get_by_role("button", name="Suche starten").click()
    page.wait_for_selector(".card", timeout=20000)
    page.wait_for_timeout(1500)
    cards = page.locator(".card").count()
    stream = page.locator(".stream-line").count()
    print(f"5. {cards} Treffer-Karten, {stream} Protokollzeilen")

    scores = page.locator(".card .criterion").all_text_contents()
    first = page.locator(".card").first
    title = first.locator(".card-title").inner_text()
    print(f"6. Erste Karte: {title[:60]}")

    values = page.evaluate("""() => Array.from(document.querySelectorAll('.card'))
        .map(c => parseInt(c.querySelector('svg')?.getAttribute('aria-label')?.match(/\\d+/)?.[0] ?? '0'))""")
    print(f"7. Sortierung absteigend: {values[:6]} -> {'ok' if values == sorted(values, reverse=True) else 'FEHLER'}")

    first.locator("text=Beleg").click()
    page.wait_for_timeout(400)
    print(f"8. Beleg aufklappbar: {'ok' if page.locator('.evidence').count() > 0 else 'FEHLER'}")

    page.reload()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    print(f"9. Nach Reload noch {page.locator('.card').count()} Karten da")

    page.get_by_label("Abmelden").click()
    page.wait_for_selector("text=Praktikums-Matcher", timeout=8000)
    page.wait_for_timeout(600)
    print(f"10. Abmelden führt zum Anmeldebildschirm: {'ok' if page.locator('.auth-card').count() == 1 else 'FEHLER'}")

    browser.close()

print("\nKonsolenfehler:", errors if errors else "keine")
