"""
Web Scraping Script

Scrapes a single website and extracts structured data based on CSS selectors.
Handles rate limiting, retries, and robots.txt compliance.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from requests.exceptions import HTTPError, Timeout

from execution.core import get_config
from execution.http_client import get

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f'.tmp/scrape_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TIMEOUT = int(get_config().get("SCRAPE_TIMEOUT"))
MAX_RETRIES = 3
MAX_PAGE_SIZE = 10 * 1024 * 1024  # 10MB
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
]


def check_robots_txt(url: str, user_agent: str) -> bool:
    """
    Check if scraping is allowed by robots.txt.

    Args:
        url: The URL to check
        user_agent: The user agent string

    Returns:
        bool: True if allowed, False otherwise
    """
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()

        is_allowed = rp.can_fetch(user_agent, url)
        logger.info(f"robots.txt check: {'allowed' if is_allowed else 'disallowed'}")
        return is_allowed

    except Exception as e:
        logger.warning(f"Could not check robots.txt: {e}. Proceeding with caution.")
        return True  # If robots.txt can't be read, proceed but log warning


def scrape_website(url: str, selectors: dict[str, str] | None = None, respect_robots: bool = True) -> dict[str, Any]:
    """
    Scrape a website and extract data based on CSS selectors.

    Args:
        url: The URL to scrape
        selectors: Dictionary mapping field names to CSS selectors
        respect_robots: Whether to check robots.txt (default: True)

    Returns:
        dict: Scraped data with metadata

    Raises:
        ValueError: If URL is invalid
        RuntimeError: If scraping fails
    """
    logger.info(f"Starting scrape of {url}")

    # Validate URL
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")

    # Use default selectors if none provided
    if selectors is None:
        selectors = {"title": "title", "headings": "h1, h2, h3", "paragraphs": "p"}

    # Random user agent to avoid blocking
    import random

    user_agent = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    # Check robots.txt if required
    if respect_robots and not check_robots_txt(url, user_agent):
        raise RuntimeError(f"Scraping disallowed by robots.txt: {url}")

    # Attempt to fetch with retries
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Fetch attempt {attempt + 1}/{MAX_RETRIES}")

            response = get(url, headers=headers, timeout=DEFAULT_TIMEOUT, stream=True)

            # Check content length
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_PAGE_SIZE:
                raise RuntimeError(f"Page too large: {content_length} bytes (max: {MAX_PAGE_SIZE})")

            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.content, "lxml")

            # Extract data based on selectors
            extracted_data = {}
            for field_name, selector in selectors.items():
                elements = soup.select(selector)
                if elements:
                    if len(elements) == 1:
                        extracted_data[field_name] = elements[0].get_text(strip=True)
                    else:
                        extracted_data[field_name] = [el.get_text(strip=True) for el in elements]
                else:
                    logger.warning(f"No elements found for selector '{selector}'")
                    extracted_data[field_name] = None

            # Build result
            result = {
                "url": url,
                "scraped_at": datetime.now().isoformat(),
                "data": extracted_data,
                "metadata": {
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type"),
                    "content_length": len(response.content),
                },
            }

            logger.info(f"Successfully scraped {url}")
            return result

        except HTTPError as e:
            if e.response.status_code == 429:  # Rate limited
                wait_time = 2**attempt  # Exponential backoff
                logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"HTTP error: {e}") from e

        except Timeout:
            logger.warning(f"Timeout on attempt {attempt + 1}")
            if attempt == MAX_RETRIES - 1:
                raise RuntimeError(f"Timed out after {MAX_RETRIES} attempts")

        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise RuntimeError(f"Scraping failed: {e}") from e
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(1)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Scrape a website and extract structured data")

    parser.add_argument("url", type=str, help="URL to scrape")

    parser.add_argument(
        "--selectors",
        type=str,
        default=None,
        help='JSON string with CSS selectors (e.g., \'{"title": "h1", "content": "p"}\')',
    )

    parser.add_argument(
        "--output", type=str, default=None, help="Output file path (default: .tmp/scraped_data_[timestamp].json)"
    )

    parser.add_argument("--ignore-robots", action="store_true", help="Ignore robots.txt (use with caution)")

    return parser.parse_args()


if __name__ == "__main__":
    """Entry point when script is run from command line."""
    try:
        args = parse_arguments()

        # Parse selectors if provided
        selectors = None
        if args.selectors:
            try:
                selectors = json.loads(args.selectors)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in selectors: {e}")
                sys.exit(1)

        # Scrape website
        result = scrape_website(url=args.url, selectors=selectors, respect_robots=not args.ignore_robots)

        # Determine output file
        if args.output:
            output_file = args.output
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f".tmp/scraped_data_{timestamp}.json"

        # Ensure .tmp directory exists
        os.makedirs(".tmp", exist_ok=True)

        # Save result
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        logger.info(f"Results saved to {output_file}")
        print(f"\nSuccess! Data saved to: {output_file}")

        sys.exit(0)

    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
