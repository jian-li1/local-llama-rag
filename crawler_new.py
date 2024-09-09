from crawl4ai.chunking_strategy import RegexChunking
from crawl4ai.extraction_strategy import NoExtractionStrategy
from crawl4ai.utils import *
from crawl4ai.models import CrawlResult
from bs4 import BeautifulSoup as Soup
import argparse
import time
import logging
import json
import os
from typing import Set
import queue
from urllib.parse import urlparse, urljoin
import requests

total_docs = 0
start = time.time()

logging.basicConfig(format='[%(levelname)s] %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

crawler_queue = queue.Queue()

def get_time():
    return time.strftime('%H:%M:%S', time.gmtime(time.time() - start))

def process_html(url: str, html: str) -> CrawlResult:
    # Extract content from HTML
    for css in args.css:
        try:
            result = get_content_of_website_optimized(url=url, html=html, word_count_threshold=5, css_selector=css, only_text=False)
            break
        except InvalidCSSSelectorError as e:
            logger.error(str(e))
        
    if not result:
        logger.error(f"{get_time()} -- Failed to extract content from {url}")
        return None
    
    cleaned_html = sanitize_input_encode(result.get("cleaned_html", ""))

    # Parse HTML into markdown and get HTML links and metadata
    markdown = sanitize_input_encode(result.get("markdown", ""))
    media = result.get("media", [])
    links = result.get("links", [])
    metadata = result.get("metadata", {})

    chunking_strategy = RegexChunking()
    extraction_strategy = NoExtractionStrategy()

    sections = chunking_strategy.chunk(markdown)
    extracted_content = extraction_strategy.run(url, sections)
    extracted_content = json.dumps(extracted_content, indent=4, default=str)

    return CrawlResult(
        url=url,
        html=html,
        cleaned_html=format_html(cleaned_html),
        markdown=markdown,
        media=media,
        links=links,
        metadata=metadata,
        screenshot=None,
        extracted_content=extracted_content,
        success=True,
        error_message="",
    )

def get_internal_links(base_url: str, html: str) -> Set:
    soup = Soup(html, "html.parser")
    # Parse all anchor tags
    anchors = soup.find_all("a", href=True)

    internal_links = set()
    for anchor in anchors:
        href = anchor["href"]
        if "#" in href:
            continue

        full_url = urljoin(base_url, href)

        if urlparse(base_url).netloc == urlparse(full_url).netloc:
            internal_links.add(full_url)

    return internal_links

def start_crawler(start_url: str):
    global total_docs
    
    # Add inital URL
    crawler_queue.put((start_url, 1))
    
    try:
        while True:
            # Get URL from queue
            if not crawler_queue.empty():
                url, depth = crawler_queue.get()
            else:
                break
            
            # Get web page from URL
            req_start = time.time()
            response = requests.get(url=url)
            total_load_time = time.time() - req_start
            if response.status_code != 200:
                logger.error(f"{get_time()} -- Failed to retrieve content from {url}")
                continue
            
            total_docs += 1
            logger.info(f"{get_time()} -- {total_docs} -- {depth} -- {url} -- {total_load_time:.2f}")
            
            # Process HTML and extract data
            result = process_html(url, response.text)
            
            filename = url.split("//", 1)[-1].replace("/", "-")
            result_dict = {"metadata": {"source": url} | result.metadata, "page_content": result.markdown}
            # Write new web page to file or update existing web page
            if not url in prev_crawled_links or not args.no_update:
                with open(f"{args.out}/{filename}.json", "w", encoding="utf-8") as f:
                    json.dump(result_dict, f, indent=4)
                    crawled_links.add(url)
            
            # Append URL to list of crawled URLs
            if not url in prev_crawled_links:
                with open(f"{args.out}/urls.txt", "a", encoding="utf-8") as f:
                    f.write(url+"\n")

            crawled_links.add(url)
            # URL might be a redirect
            if result.metadata.get("og:url"):
                crawled_links.add(result.metadata.get("og:url"))
            
            # Get child links if max depth hasn't exceeded
            if depth < args.depth:
                for link in get_internal_links(url, result.html):
                    # Prevent duplicate URLs
                    if link in crawled_links:
                        continue
                    # URL isn't part of specified base URL
                    elif not link.startswith(args.base.rstrip("/")):
                        continue
                    # Exclude subdirectories that contain the provided list of strings
                    elif args.exclude and any([s in link.split("//", 1)[-1] for s in args.exclude]):
                        continue
                
                    # Add to queue
                    crawler_queue.put((link, depth+1))
                    # Add URL to set of crawled links
                    crawled_links.add(link)
    except (Exception, KeyboardInterrupt) as e:
        print(repr(e))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawls websites from the base URL and store all web content into individual JSON files.")
    parser.add_argument("--url", type=str, required=True, help="The initial URLs to crawl from")
    parser.add_argument("--base", type=str, required=True, help="The base URL to prevent crawling external links")
    parser.add_argument("--out", type=str, required=True, help="The directory to store the web content")
    parser.add_argument("--depth", type=int, default=2, help="The max depth of the recursive crawling")
    parser.add_argument("--css", nargs="*", help="Filter content with CSS selectors. Allows multiple CSS selectors but prioritizes first selector. \
                        If first selector not found in web page, falls back to subsequent selectors. \
                        Default selector is 'div'.")
    parser.add_argument("--exclude", nargs="*", help="Exclude subdirectories that contain the provided list of strings")
    parser.add_argument("--no-update", action="store_true", help="Do not update previously crawled links")
    args = parser.parse_args()

    args.css = ["div"] if not args.css else args.css + ["div"]
    print(f"CSS selectors: {args.css}")
    print(f"Exclude substrings: {args.exclude}")
    print(f"Update existing documents: {not args.no_update}")

    prev_crawled_links = set()
    crawled_links = set()
    if os.path.isfile(f"{args.out}/urls.txt"):
        # Do not append URLs that were already crawled
        with open(f"{args.out}/urls.txt") as f:
            prev_crawled_links = set(f.read().splitlines())

    try:
        start_crawler(start_url=args.url)
    except (KeyboardInterrupt) as e:
        print(repr(e))

    logger.info(f"{get_time()} -- Finished")
