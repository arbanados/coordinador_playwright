from pathlib import Path
from datetime import datetime
import asyncio
import os
import sys
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TIMEOUT = 60_000  # ms

date_suffix = datetime.now().strftime("-%m-%d")
downloads_dir = Path("downloads")
downloads_dir.mkdir(exist_ok=True)

def log(msg: str):
    print(f"[SCRAPER] {msg}", flush=True)

async def run():
    log(f"Starting. HEADLESS={HEADLESS}, CWD={Path('.').resolve()}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
        page.set_default_timeout(TIMEOUT)

        # Collect useful debugging info
        page.on("console", lambda m: print(f"[BROWSER CONSOLE] {m.type}: {m.text}", flush=True))
        page.on("pageerror", lambda e: print(f"[BROWSER PAGEERROR] {e}", flush=True))
        page.on("requestfailed", lambda r: print(f"[REQ FAILED] {r.method} {r.url} -> {r.failure}", flush=True))

        # Start Playwright tracing (screenshots + DOM snapshots)
        await context.tracing.start(screenshots=True, snapshots=True, sources=True)

        try:
            # 1) Open page
            log("Navigating to costos-marginales page…")
            await page.goto("https://www.coordinador.cl/costos-marginales/", wait_until="load")
            log("Page loaded.")

            # 2) Click the 'Costo Marginal Programado' link
            log("Waiting for 'Costo Marginal Programado' link…")
            link = page.get_by_role("link", name="Costo Marginal Programado")
            await link.wait_for(state="visible")
            log("Clicking the link…")
            await link.click()

            # 3) Wait for the PowerBI iframe to appear and get its content frame
            log("Waiting for PowerBI iframe…")
            iframe_elem = await page.wait_for_selector("#Costo-Marginal-Programado iframe", timeout=TIMEOUT)
            frame = await iframe_elem.content_frame()
            if frame is None:
                raise RuntimeError("Iframe content_frame() returned None")

            # 4) Wait for the 'Descargar' button inside the iframe
            log("Waiting for 'Descargar' button inside iframe…")
            descargar = frame.get_by_title("Descargar").first
            await descargar.wait_for(state="visible")
            log("Taking pre-download screenshot as 'page.png'…")
            await page.screenshot(path="page.png", full_page=True)

            # 5) Trigger download
            log("Clicking 'Descargar' and waiting for download…")
            try:
                async with page.expect_download() as dl_info:
                    await descargar.click()
                download = await dl_info.value
            except PlaywrightTimeoutError:
                raise RuntimeError("Download did not start within timeout")

            # 6) Save file
            suggested = download.suggested_filename
            log(f"Download started. Suggested filename: {suggested}")
            save_path = downloads_dir / suggested
            await download.save_as(str(save_path))
            log(f"Saved file to: {save_path.resolve()}")

            # Stop trace (success path)
            log("Stopping trace (success)…")
            await context.tracing.stop(path="trace.zip")
            await browser.close()
            log("Done.")
        except Exception as e:
            # Save as much debugging info as possible
            log(f"ERROR: {type(e).__name__}: {e}")
            try:
                await page.screenshot(path="page-error.png", full_page=True)
                log("Saved 'page-error.png'")
            except Exception as se:
                log(f"Could not take error screenshot: {se}")
            try:
                log("Stopping trace (failure)…")
                await context.tracing.stop(path="trace.zip")
            except Exception as te:
                log(f"Could not save trace: {te}")
            try:
                await browser.close()
            except Exception:
                pass
            # Make the job fail
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run())

