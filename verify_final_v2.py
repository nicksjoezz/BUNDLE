import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('http://localhost:5000')
        await page.wait_for_timeout(2000)

        # Take screenshot of dashboard
        await page.screenshot(path='final_dash_v2.png')

        # Check Sell tab for liquidation buttons
        await page.click('button:has-text("SL")')
        await page.wait_for_timeout(1000)
        await page.screenshot(path='final_sell_v2.png')

        # Check Operations tab
        await page.click('button:has-text("OP")')
        await page.wait_for_timeout(1000)
        await page.screenshot(path='final_ops_v2.png')

        await browser.close()

asyncio.run(run())
