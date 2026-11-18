import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class RSSFetcher:
    """RSS 2.0 및 Atom 피드를 파싱하여 정규화된 딕셔너리 리스트로 반환"""

    def __init__(self, timeout: int = 8):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

    def fetch_feed(self, feed_meta: dict) -> List[Dict]:
        name = feed_meta["name"]
        url = feed_meta["url"]
        default_cat = feed_meta.get("default_category", "IT 일반")
        items = []

        logging.info(f"Fetching RSS feed: {name} ({url})")
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                content = response.read()
                root = ET.fromstring(content)

                # 1. RSS 2.0 지원 (<channel><item>...)
                channel = root.find("channel")
                if channel is not None:
                    for item in channel.findall("item"):
                        title = item.findtext("title", "")
                        link = item.findtext("link", "")
                        desc = item.findtext("description", "")
                        pub_date = item.findtext("pubDate", "")
                        if title and link:
                            items.append({
                                "title": title,
                                "link": link,
                                "description": desc,
                                "published": pub_date,
                                "source": name,
                                "default_category": default_cat
                            })
                    return items

                # 2. Atom 피드 지원 (<feed><entry>...)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                entries = root.findall("atom:entry", ns) or root.findall("entry")
                for entry in entries:
                    title = entry.findtext("atom:title", "", ns) or entry.findtext("title", "")
                    link_elem = entry.find("atom:link", ns) or entry.find("link")
                    link = link_elem.get("href", "") if link_elem is not None else ""
                    summary = entry.findtext("atom:summary", "", ns) or entry.findtext("summary", "") or entry.findtext("content", "")
                    pub_date = entry.findtext("atom:updated", "", ns) or entry.findtext("updated", "")
                    if title and link:
                        items.append({
                            "title": title,
                            "link": link,
                            "description": summary,
                            "published": pub_date,
                            "source": name,
                            "default_category": default_cat
                        })
                return items

        except Exception as e:
            logging.warning(f"Failed to fetch {name} ({url}): {e}")
            return []
