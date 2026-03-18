import os
import json
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

class UniversalCrawler:
    def __init__(self):
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 각 매거진별 설정 (URL과 기사 링크 판별 키워드)
        self.targets = [
            {"name": "allure", "url": "https://www.allure.com/hair-ideas", "base": "https://www.allure.com", "keywords": ["/story/", "/gallery/"]},
            {"name": "byrdie", "url": "https://www.byrdie.com/hair-styling-4628405", "base": "https://www.byrdie.com", "keywords": ["hair"]},
            {"name": "marieclaire", "url": "https://www.marieclaire.com/beauty/hair/", "base": "https://www.marieclaire.com", "keywords": ["/beauty/", "hair"]},
            {"name": "harpersbazaar", "url": "https://www.harpersbazaar.com/beauty/hair/", "base": "https://www.harpersbazaar.com", "keywords": ["/beauty/hair/a"]},
            {"name": "instyle", "url": "https://www.instyle.com/hair", "base": "https://www.instyle.com", "keywords": ["hair"]},
            {"name": "glamour", "url": "https://www.glamour.com/beauty/hair", "base": "https://www.glamour.com", "keywords": ["/story/", "/gallery/"]},
            {"name": "vogue", "url": "https://www.vogue.com/beauty/hair", "base": "https://www.vogue.com", "keywords": ["/article/"]},
            {"name": "whowhatwear", "url": "https://www.whowhatwear.com/beauty/hair", "base": "https://www.whowhatwear.com", "keywords": ["/beauty/hair/"]},
            {"name": "elle", "url": "https://www.elle.com/beauty/hair/", "base": "https://www.elle.com", "keywords": ["/beauty/hair/a", "/beauty/"]},
            {"name": "trendspotter_women", "url": "https://www.thetrendspotter.net/category/womens-hairstyles/", "base": "https://www.thetrendspotter.net", "keywords": ["hair"]},
            {"name": "gq", "url": "https://www.gq.com/about/hair", "base": "https://www.gq.com", "keywords": ["/story/", "/gallery/"]},
            {"name": "trendspotter_men", "url": "https://www.thetrendspotter.net/category/mens-hairstyles/", "base": "https://www.thetrendspotter.net", "keywords": ["hair"]},
            # 헤어 전문가용/글로벌 등 7개 소스 추가 반영
            {"name": "americansalon", "url": "https://www.americansalon.com/hair-0", "base": "https://www.americansalon.com", "keywords": ["/hair/"]},
            {"name": "beautylaunchpad_cut", "url": "https://www.beautylaunchpad.com/cut", "base": "https://www.beautylaunchpad.com", "keywords": ["/cut/"]},
            {"name": "beautylaunchpad_color", "url": "https://www.beautylaunchpad.com/color", "base": "https://www.beautylaunchpad.com", "keywords": ["/color/"]},
            {"name": "beautylaunchpad_styles", "url": "https://www.beautylaunchpad.com/styles", "base": "https://www.beautylaunchpad.com", "keywords": ["/styles/"]},
            {"name": "hypehair", "url": "https://hypehair.com/category/hair/", "base": "https://hypehair.com", "keywords": ["hair", "/20"]},
            {"name": "hji", "url": "https://hji.co.uk/trends", "base": "https://hji.co.uk", "keywords": ["/trends/"]},
            {"name": "esteticamagazine", "url": "https://www.esteticamagazine.com/category/trends/hair-collection/", "base": "https://www.esteticamagazine.com", "keywords": ["/trends", "/hair", "collection"]},
            # 한국 매거진 8개 소스
            {"name": "wkorea", "url": "https://www.wkorea.com/beauty/", "base": "https://www.wkorea.com", "keywords": ["/beauty/"]},
            {"name": "elle_korea", "url": "https://www.elle.co.kr/beauty", "base": "https://www.elle.co.kr", "keywords": ["/beauty/"]},
            {"name": "vogue_korea", "url": "https://www.vogue.co.kr/beauty/", "base": "https://www.vogue.co.kr", "keywords": ["/beauty/"]},
            {"name": "harpersbazaar_korea", "url": "https://www.harpersbazaar.co.kr/beauty", "base": "https://www.harpersbazaar.co.kr", "keywords": ["/beauty/"]},
            {"name": "marieclaire_korea", "url": "https://www.marieclairekorea.com/category/beauty/beauty_trend/", "base": "https://www.marieclairekorea.com", "keywords": ["/beauty/", "/category/"]},
            {"name": "gq_korea", "url": "https://www.gqkorea.co.kr/style/grooming/", "base": "https://www.gqkorea.co.kr", "keywords": ["/style/", "/grooming/"]},
            {"name": "cosmopolitan_korea", "url": "https://www.cosmopolitan.co.kr/beauty", "base": "https://www.cosmopolitan.co.kr", "keywords": ["/beauty/"]},
            {"name": "allure_korea", "url": "https://www.allurekorea.com/beauty/hair/", "base": "https://www.allurekorea.com", "keywords": ["/beauty/", "/hair/"]}
        ]

    def _is_article_link(self, href, keywords, base_url):
        if not href:
            return False
            
        # exclude basic navigation/category pages
        excludes = ['/about/', '/contact', '/privacy', 'author', 'tag', '/category/', '?page=', 'newsletter', 'subscribe']
        href_lower = href.lower()
        if any(exc in href_lower for exc in excludes):
            return False
            
        # if keywords provided, must contain at least one
        if keywords and keywords[0] != "/":
            if not any(kw in href for kw in keywords):
                return False
                
        # heuristic: article URLs are usually long
        if len(href.split('/')) < 4 and len(href) < 30:
            return False
            
        return True

    def _extract_body_text(self, soup):
        """본문 텍스트 추출 - 여러 전략으로 시도"""
        # 전략 1: article 태그
        article = soup.find('article')
        if article:
            paragraphs = [p.get_text(strip=True) for p in article.find_all('p') if p.get_text(strip=True)]
            if paragraphs:
                return paragraphs

        # 전략 2: 본문 영역 class/id 탐색 (한국 사이트 대응)
        body_selectors = [
            {'class_': lambda c: c and any(k in str(c).lower() for k in ['article-body', 'post-content', 'entry-content', 'article_body', 'article-content', 'content-body', 'story-body'])},
            {'class_': lambda c: c and any(k in str(c).lower() for k in ['detail', 'view_cont', 'article_cont', 'news_body', 'article_view'])},
        ]
        for sel in body_selectors:
            container = soup.find('div', **sel)
            if container:
                paragraphs = [p.get_text(strip=True) for p in container.find_all('p') if p.get_text(strip=True)]
                if paragraphs:
                    return paragraphs

        # 전략 3: 모든 p 태그에서 긴 텍스트만 수집
        all_p = soup.find_all('p')
        paragraphs = [p.get_text(strip=True) for p in all_p if len(p.get_text(strip=True)) > 30]
        if paragraphs:
            return paragraphs

        return []

    def parse_article(self, html, source_name):
        soup = BeautifulSoup(html, 'html.parser')
        items = []

        # 불필요한 요소 제거
        for tag in soup.find_all(['nav', 'footer', 'header', 'aside', 'script', 'style', 'iframe']):
            tag.decompose()

        # 제목 추출: h1 → og:title → title 태그
        title_elem = soup.find('h1')
        main_title = title_elem.get_text(strip=True) if title_elem else ""
        if not main_title:
            og_title = soup.find('meta', property='og:title')
            if og_title:
                main_title = og_title.get('content', '')
        if not main_title:
            t = soup.find('title')
            if t:
                main_title = t.get_text(strip=True)

        year = str(datetime.now().year)

        # h2, h3 기반 갤러리/리스트 형태 파싱
        headings = soup.find_all(['h2', 'h3'])

        if len(headings) >= 2: # listicle
            for heading in headings:
                trend_name = heading.get_text(strip=True)
                if len(trend_name) > 100 or len(trend_name) < 3:
                     continue

                desc_paragraphs = []
                # find_next (sibling이 아닌 전체 다음 요소) 로 탐색 - div 래핑 대응
                for elem in heading.find_all_next():
                    if elem.name in ['h2', 'h3', 'h1']:
                        break
                    if elem.name == 'p':
                        text = elem.get_text(strip=True)
                        if text and len(text) > 10:
                            desc_paragraphs.append(text)

                if desc_paragraphs:
                    items.append({
                        "trend_name": trend_name,
                        "year": year,
                        "hairstyle_text": "",
                        "color_text": "",
                        "description": "\n".join(desc_paragraphs),
                        "source": source_name
                    })

        # 리스트 형태가 아니라면 전체 본문 추출
        if not items and main_title:
            paragraphs = self._extract_body_text(soup)

            # 본문이 너무 짧으면 제외
            body = "\n".join(paragraphs)
            if len(body) > 100:
                items.append({
                    "trend_name": main_title,
                    "year": year,
                    "hairstyle_text": "",
                    "color_text": "",
                    "description": body,
                    "source": source_name
                })

        return items

    def crawl(self):
        print("======== [Universal Crawler] 모든 매거진 크롤링 시작 ========")
        
        with sync_playwright() as p:
            # 안티 크롤링 우회를 위해 브라우저 설정 추가
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()

            for target in self.targets:
                name = target['name']
                url = target['url']
                base_url = target['base']
                keywords = target['keywords']
                
                print(f"\n--- [{name}] 탐색 시작 ({url}) ---")
                
                try:
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    time.sleep(3)

                    # 스크롤해서 추가 콘텐츠 로드 유도
                    for scroll_y in [1000, 2000, 3000]:
                        page.mouse.wheel(0, scroll_y)
                        time.sleep(1)
                    
                    html = page.content()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    links = set()
                    for a in soup.find_all('a', href=True):
                        href = a['href']
                        if self._is_article_link(href, keywords, base_url):
                            full_url = href if href.startswith('http') else base_url + href
                            links.add(full_url)
                            
                    target_links = list(links)[:8] # 각 카테고리별 최대 8개 기사 탐색
                    
                    if not target_links:
                        print(f"[{name}] 기사 링크를 찾지 못했습니다.")
                        continue
                        
                    results = []
                    for act_url in target_links:
                        print(f"  -> [{name}] 수집 중: {act_url}")
                        try:
                            page.goto(act_url, timeout=30000, wait_until="domcontentloaded")
                            time.sleep(2)
                            # lazy loading 대응
                            page.mouse.wheel(0, 1500)
                            time.sleep(1)
                            
                            art_html = page.content()
                            items = self.parse_article(art_html, name.capitalize())
                            results.extend(items)
                        except Exception as e:
                            print(f"  -> [{name}] 페이지 수집 에러 ({act_url}): {e}")
                            
                    # 중복 제거
                    unique_results = []
                    seen = set()
                    for r in results:
                        key = r['trend_name'] + str(r['description'])[:30]
                        if key not in seen:
                            seen.add(key)
                            unique_results.append(r)
                            
                    output_path = os.path.join(self.data_dir, f'{name}.json')
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(unique_results, f, ensure_ascii=False, indent=2)
                    print(f"--- [{name}] 완료. {len(unique_results)}개 아이템 저장됨 ---")

                except Exception as e:
                    print(f"[{name}] 접근 실패: {e}")
                    
            browser.close()

if __name__ == '__main__':
    UniversalCrawler().crawl()
