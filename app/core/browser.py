"""
Browser automation module using Playwright.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from app.config import settings

logger = logging.getLogger(__name__)


class BrowserManager:
    """
    Context manager for Playwright browser automation.
    Handles launching, context creation, and cleanup.
    """

    def __init__(
        self,
        headless: bool = None,
        viewport_width: int = None,
        viewport_height: int = None,
        user_agent: str = None,
    ):
        self.headless = headless if headless is not None else settings.HEADLESS
        self.viewport_width = viewport_width or settings.VIEWPORT_WIDTH
        self.viewport_height = viewport_height or settings.VIEWPORT_HEIGHT
        self.user_agent = user_agent or settings.DEFAULT_USER_AGENT

        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        """Initialize browser on context entry."""
        await self.launch()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up browser on context exit."""
        await self.close()

    async def launch(self):
        """Launch browser and create context."""
        try:
            logger.info("Launching Playwright browser...")
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            # Create incognito context
            self.context = await self.browser.new_context(
                viewport={"width": self.viewport_width, "height": self.viewport_height},
                user_agent=self.user_agent,
                ignore_https_errors=True,
            )

            # Create new page
            self.page = await self.context.new_page()

            logger.info("Browser launched successfully")
            return self

        except Exception as e:
            logger.error(f"Failed to launch browser: {str(e)}")
            await self.close()
            raise

    async def close(self):
        """Close browser and cleanup."""
        try:
            if self.page:
                await self.page.close()
                self.page = None

            if self.context:
                await self.context.close()
                self.context = None

            if self.browser:
                await self.browser.close()
                self.browser = None

            if self.playwright:
                await self.playwright.stop()
                self.playwright = None

            logger.info("Browser closed successfully")

        except Exception as e:
            logger.error(f"Error closing browser: {str(e)}")

    async def navigate_to(self, url: str) -> Dict[str, Any]:
        """
        Navigate to a URL and capture page state.

        Returns:
            Dict with url, title, and screenshot data
        """
        if not self.page:
            raise RuntimeError("Browser not initialized")

        try:
            logger.info(f"Navigating to: {url}")
            response = await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for page to stabilize
            await asyncio.sleep(2)

            # Get page info
            page_info = {
                "url": self.page.url,
                "title": await self.page.title(),
                "status": response.status if response else None,
            }

            logger.info(f"Navigated to: {page_info['url']}")
            return page_info

        except Exception as e:
            logger.error(f"Navigation failed: {str(e)}")
            raise

    async def capture_state(self) -> Dict[str, Any]:
        """
        Capture current page state including DOM, accessibility tree, and screenshot.

        Returns:
            Dict with page state data
        """
        if not self.page:
            raise RuntimeError("Browser not initialized")

        try:
            # Get DOM tree (simplified)
            dom_tree = await self.page.evaluate("""
                () => {
                    const getVisibleText = (el) => {
                        return el.innerText || '';
                    };

                    const getElementInfo = (el) => {
                        const rect = el.getBoundingClientRect();
                        return {
                            tag: el.tagName.toLowerCase(),
                            id: el.id,
                            className: el.className,
                            text: getVisibleText(el).substring(0, 100),
                            visible: rect.width > 0 && rect.height > 0,
                            href: el.href || null,
                            type: el.type || null,
                            name: el.name || null,
                            placeholder: el.placeholder || null,
                        };
                    };

                    // Get interactive elements
                    const interactiveSelectors = [
                        'a', 'button', 'input', 'select', 'textarea',
                        '[role="button"]', '[role="link"]', '[tabindex]'
                    ];

                    const elements = [];
                    interactiveSelectors.forEach(selector => {
                        try {
                            document.querySelectorAll(selector).forEach(el => {
                                if (el.offsetParent !== null) {  // visible
                                    elements.push(getElementInfo(el));
                                }
                            });
                        } catch (e) {}
                    });

                    return {
                        url: window.location.href,
                        title: document.title,
                        elements: elements.slice(0, 50),  # Limit to 50 elements
                    };
                }
            """)

            # Get accessibility tree
            accessibility_tree = await self.page.accessibility.snapshot()

            # Take screenshot
            screenshot_bytes = await self.page.screenshot(type="png", full_page=False)
            screenshot_base64 = screenshot_bytes.base64 if hasattr(screenshot_bytes, 'base64') else None

            state = {
                "url": self.page.url,
                "title": await self.page.title(),
                "dom_tree": dom_tree,
                "accessibility_tree": accessibility_tree,
                "screenshot_base64": screenshot_base64,
                "viewport": {"width": self.viewport_width, "height": self.viewport_height},
            }

            return state

        except Exception as e:
            logger.error(f"Failed to capture state: {str(e)}")
            raise

    async def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an action on the page.

        Args:
            action: Dict with action_type, target, value, etc.

        Returns:
            Dict with success status and result
        """
        if not self.page:
            raise RuntimeError("Browser not initialized")

        action_type = action.get("action_type", action.get("action"))
        target = action.get("target")
        value = action.get("value")

        logger.info(f"Executing action: {action_type} on {target}")

        try:
            result = {"success": False, "error": None}

            if action_type == "click":
                # Try to find element and click
                await self.page.click(target, timeout=5000)
                result["success"] = True

            elif action_type == "type":
                # Clear and type
                await self.page.fill(target, value or "")
                result["success"] = True

            elif action_type == "scroll":
                # Scroll the page
                direction = value or "down"
                if direction == "down":
                    await self.page.evaluate("window.scrollBy(0, 500)")
                else:
                    await self.page.evaluate("window.scrollBy(0, -500)")
                result["success"] = True

            elif action_type == "hover":
                await self.page.hover(target, timeout=5000)
                result["success"] = True

            elif action_type == "navigate":
                await self.page.goto(value, wait_until="domcontentloaded")
                result["success"] = True

            elif action_type == "wait":
                await asyncio.sleep(float(value or 2))
                result["success"] = True

            else:
                result["error"] = f"Unknown action type: {action_type}"

            # Small delay after action
            await asyncio.sleep(0.5)

            return result

        except Exception as e:
            logger.error(f"Action failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def get_element_at_position(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        """Get element info at given position."""
        try:
            return await self.page.evaluate(
                """([x, y]) => {
                    const el = document.elementFromPoint(x, y);
                    if (!el) return null;
                    return {
                        tag: el.tagName.toLowerCase(),
                        id: el.id,
                        className: el.className,
                        text: el.innerText?.substring(0, 50),
                        href: el.href,
                    };
                }""",
                [x, y],
            )
        except Exception as e:
            logger.error(f"Failed to get element at position: {str(e)}")
            return None
