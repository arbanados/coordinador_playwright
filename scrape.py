from pathlib import Path
from datetime import datetime
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

HEADLESS = False
date_suffix = datetime.now().strftime("-%m-%d")  # e.g., "-08-26"
downloads_dir = Path("downloads")
downloads_dir.mkdir(exist_ok=True)

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        # 1) Go to page + open "Costo Marginal Programado"
        await page.goto("https://www.coordinador.cl/costos-marginales/", wait_until="load")
        await page.get_by_role("link", name="Costo Marginal Programado").click()

        # 2) Target the PowerBI iframe
        frame = page.frame_locator("#Costo-Marginal-Programado iframe").nth(1)

        # 3) Trigger download from button inside iframe
        try:
            async with page.expect_download() as dl_info:
                await frame.get_by_title("Descargar").click()
            download = await dl_info.value
        except PlaywrightTimeoutError:
            print("Download failed or timed out")
            await browser.close()
            return

        # 4) Save file
        save_path = downloads_dir / download.suggested_filename
        await download.save_as(str(save_path))
        print(f"Saved file to: {save_path.resolve()}")

        await browser.close()
await run()  # Jupyter supports top-level `await`
