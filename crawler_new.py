from crawl4ai import AsyncWebCrawler
from bs4 import BeautifulSoup as Soup
import argparse
import time
import logging
import json
import os
import asyncio
from typing import Set
import queue
from urllib.parse import urlparse, urljoin

# lock = threading.Lock()
# stop_event = threading.Event()

total_docs = 0
start = time.time()

logging.basicConfig(format='[%(levelname)s] %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

crawler_queue = queue.Queue()

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

async def start_crawler(start_url: str):
    global total_docs
    
    crawler_queue.put((start_url, 1))

    async with AsyncWebCrawler(verbose=args.verbose, always_by_pass_cache=True) as crawler:
        try:
            while True:
                # Get URL from queue
                if not crawler_queue.empty():
                    url, depth = crawler_queue.get()
                    total_docs += 1

                    time_str = time.strftime('%H:%M:%S', time.gmtime(time.time() - start))
                    logger.info(f"{time_str} -- {total_docs} -- {depth} -- {url}")
                else:
                    break
                
                # Get page content and filter content by CSS selector
                # If parsing error, fall back to subsequent CSS selectors
                for css in args.css:
                    result = await crawler.arun(url=url, css_selector=css, verbose=args.verbose)
                    if result.success:
                        break

                # Skip URL if request still fails
                if not result.success:
                    continue
                
                filename = url.split("//", 1)[-1].replace("/", "-")
                result_dict = {"metadata": result.metadata | {"source": url}, "page_content": result.markdown}

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
    
    logger.info(f"Finished")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawls websites from the base URL and store all web content into individual JSON files.")
    parser.add_argument("--url", type=str, required=True, help="The initial URL to crawl from")
    parser.add_argument("--base", type=str, required=True, help="The base URL to prevent crawling external links")
    parser.add_argument("--out", type=str, required=True, help="The directory to store the web content")
    parser.add_argument("--depth", type=int, default=2, help="The max depth of the recursive crawling")
    parser.add_argument("--css", nargs="*", help="Filter content with CSS selectors. Allows multiple CSS selectors but prioritizes first selector. \
                        If first selector not found in web page, falls back to subsequent selectors. \
                        Default selector is 'div'.")
    parser.add_argument("--exclude", nargs="*", help="Exclude subdirectories that contain the provided list of strings")
    parser.add_argument("--no-update", action="store_true", help="Do not update previously crawled links")
    parser.add_argument("--verbose", action="store_true", default=False)
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

    asyncio.run(start_crawler(args.url))

    logger.info(f"Finished: {(time.time() - start) / 60:.2f} minutes")
