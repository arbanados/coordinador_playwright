from pathlib import Path
from datetime import datetime
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import os

HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

date_suffix = datetime.now().strftime("-%m-%d")
downloads_dir = Path("downloads")
downloads_dir.mkdir(exist_ok=True)

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        # Be generous with timeouts in CI
        page.set_default_timeout(45_000)

        # 1) Open page and click "Costo Marginal Programado"
        await page.goto("https://www.coordinador.cl/costos-marginales/", wait_until="load")
        await page.get_by_role("link", name="Costo Marginal Programado").click()

        # 2) Target the PowerBI iframe (wait for it to be attached)
        frame_loc = page.frame_locator("#Costo-Marginal-Programado iframe").nth(1)
        # Make sure the iframe content is ready by waiting for a common control
        await frame_loc.get_by_title("Descargar").first.wait_for()

        # 3) Trigger download from button inside iframe
        try:
            async with page.expect_download() as dl_info:
                await frame_loc.get_by_title("Descargar").first.click()
            download = await dl_info.value
        except PlaywrightTimeoutError:
            print("Download failed or timed out")
            await browser.close()
            raise SystemExit(1)

        # 4) Save file
        save_path = downloads_dir / download.suggested_filename
        await download.save_as(str(save_path))
        print(f"Saved file to: {save_path.resolve()}")

        await browser.close()

asyncio.run(run())
