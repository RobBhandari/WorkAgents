# Scrape Website

## Goal
Extract structured data from a single website URL and save it to a standardized format for further processing.

## Inputs
Required:
- **URL**: The website URL to scrape (must be valid HTTP/HTTPS URL)
- **Data to Extract**: Specification of what data points to extract (CSS selectors, XPath, or natural language description)

Optional:
- **Output Format**: JSON (default) or CSV
- **Rate Limit Delay**: Seconds to wait between requests (default: 1)
- **User Agent**: Custom user agent string (default: uses library default)

## Tools/Scripts to Use
- `execution/scrape_single_site.py` - Main scraping script that handles HTTP requests, HTML parsing, and data extraction

## Outputs
- **Format**: JSON file by default (can be CSV)
- **Location**: `.tmp/scraped_data_[timestamp].json`
- **Structure**:
  ```json
  {
    "url": "scraped_url",
    "scraped_at": "ISO8601 timestamp",
    "data": {
      // Extracted data fields
    },
    "metadata": {
      "status_code": 200,
      "content_type": "text/html"
    }
  }
  ```

## Process Flow
1. Validate the input URL format
2. Call `execution/scrape_single_site.py` with URL and extraction parameters
3. Script fetches the webpage with appropriate headers
4. Parse HTML and extract specified data points
5. Save structured data to `.tmp/` directory
6. Return file path and summary of extracted data

## Edge Cases
- **Rate Limits**: If rate limited (HTTP 429), script will retry with exponential backoff (max 3 retries)
- **Authentication Required**: If site requires login (HTTP 401/403), script will fail with clear error message - user must provide authenticated session cookies
- **JavaScript-Required Sites**: Basic scraping doesn't execute JavaScript. For JS-heavy sites, consider using Selenium or Playwright
- **Timeouts**: Network timeout set to 30 seconds. For slow sites, this can be increased via environment variable `SCRAPE_TIMEOUT`
- **Invalid Selectors**: If CSS selectors don't match any elements, script logs warning and returns empty data fields
- **Robots.txt Compliance**: Script checks robots.txt before scraping. Will error if disallowed.
- **Large Pages**: Pages over 10MB are rejected to prevent memory issues

## Learnings
- **2024-01**: Discovered that some sites block requests with default Python user agent. Now using randomized browser user agents.
- **2024-02**: API endpoint added retry logic after encountering intermittent connection failures.
- **2024-03**: Added robots.txt checking after feedback about ethical scraping practices.

---

**Created**: 2024-01-15
**Last Updated**: 2024-03-20
**Status**: Active
