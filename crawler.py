"""
crawler.py — 당근마켓 동네업체 전화번호 크롤러
  · 지역(시도→구군→동) + 카테고리 기반 수집
  · 010 번호 우선 추출 / 안심번호(050) 포함
  · 프록시 로테이션 지원
"""

import re, sys, time, random, logging, requests, html as _html
from typing import Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

from proxy_manager import ProxyManager, ProxyEntry

logger = logging.getLogger("daangn_crawler")

# ── 상수 ─────────────────────────────────────────────────
BASE_URL   = "https://www.daangn.com"
SEARCH_URL = f"{BASE_URL}/kr/local-profile/s/"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# ── 카테고리 ─────────────────────────────────────────────
CATEGORIES = {
    "전체":        "",
    "음식점":      "FOOD_AND_BEVERAGES",
    "카페/디저트": "CAFE_AND_BAKERY",
    "뷰티/미용":   "BEAUTY",
    "운동/스포츠": "SPORTS_AND_FITNESS",
    "교육":        "EDUCATION",
    "병원/의원":   "MEDICAL",
    "반려동물":    "PET",
    "인테리어":    "INTERIOR",
    "자동차":      "AUTOMOBILE",
    "청소":        "CLEANING",
    "세탁":        "LAUNDRY",
    "사진":        "PHOTO",
    "여행/숙박":   "TRAVEL",
    "부동산":      "REAL_ESTATE",
    "기타":        "OTHER",
}

DEFAULT_KEYWORDS = [
    "음식점","카페","미용실","헬스장","학원","병원","약국",
    "마트","빵집","치킨","피자","분식","중국집",
    "족발","삼겹살","한식","일식","양식",
    "네일","마사지","청소","인테리어","세탁",
    "꽃집","사진관","전기","에어컨","이삿짐",
]

# ── 010 번호 판별 ─────────────────────────────────────────
def is_010(phone: str) -> bool:
    """010으로 시작하는 11자리 번호 여부"""
    p = re.sub(r"[^0-9]", "", phone)
    return p.startswith("010") and len(p) == 11

def fmt_phone(phone: str) -> str:
    """번호 포맷: 01012345678 → 010-1234-5678"""
    p = re.sub(r"[^0-9]", "", phone)
    if len(p) == 11 and p.startswith("010"):
        return f"{p[:3]}-{p[3:7]}-{p[7:]}"
    if len(p) == 10:
        return f"{p[:3]}-{p[3:6]}-{p[6:]}"
    return phone


# ── 데이터 클래스 ─────────────────────────────────────────
@dataclass
class BusinessInfo:
    name: str        = ""
    phone: str       = ""       # 실제 전화번호 (010 포함)
    safe_number: str = ""       # 안심번호 (050)
    address: str     = ""
    region: str      = ""
    category: str    = ""
    url: str         = ""
    description: str = ""

    @property
    def phone_010(self) -> str:
        """010 번호만 반환 (없으면 빈 문자열)"""
        if is_010(self.phone):
            return fmt_phone(self.phone)
        return ""

    @property
    def display_phone(self) -> str:
        """010 우선, 없으면 실제번호, 없으면 안심번호"""
        if is_010(self.phone):
            return fmt_phone(self.phone)
        if self.phone:
            return self.phone
        return self.safe_number

    def is_valid(self) -> bool:
        return bool(self.name) and bool(self.phone or self.safe_number)

    def has_010(self) -> bool:
        return bool(self.phone_010)


# ── HTML 파싱 헬퍼 ────────────────────────────────────────
def _unescape(s: str) -> str:
    result = _html.unescape(s or "")
    if "&amp;" in result:
        result = _html.unescape(result)
    return result

def _extract_links(html: str) -> list[str]:
    """목록 페이지에서 업체 상세 링크 추출"""
    pattern = r'href="(/kr/local-profile/(?!s/)[^"?#]+)"'
    links = re.findall(pattern, html)
    seen, result = set(), []
    for lnk in links:
        if lnk not in seen:
            seen.add(lnk)
            result.append(BASE_URL + lnk)
    return result

def _parse_business(html: str, url: str) -> Optional[BusinessInfo]:
    """업체 상세 페이지 파싱"""
    info = BusinessInfo(url=url)

    # 업체명·지역·카테고리 (og:title)
    og = re.search(r'og:title[^>]+content="([^"]+)"', html)
    if og:
        parts = _unescape(og.group(1)).split(" | ")
        info.name     = parts[0].strip() if parts else ""
        info.region   = parts[1].strip() if len(parts) >= 2 else ""
        info.category = parts[2].strip() if len(parts) >= 3 else ""

    # 실제 전화번호
    m = re.search(r'"phone":"([^"]+)"', html)
    if m: info.phone = m.group(1)

    # 안심번호
    m = re.search(r'"safeNumber":"([^"]+)"', html)
    if m:
        info.safe_number = m.group(1)
    else:
        m = re.search(r'"telephone":"([^"]+)"', html)
        if m: info.safe_number = m.group(1)

    # 주소
    m = re.search(r'"streetAddress":"([^"]+)"', html)
    if m:
        info.address = m.group(1)
    else:
        m = re.search(r'"road":"([^"]{5,100})"', html)
        if m: info.address = m.group(1)

    # 설명
    m = re.search(r'"description":"([^"]{5,300})"', html)
    if m: info.description = _unescape(m.group(1))

    return info if info.is_valid() else None


# ── 메인 크롤러 ──────────────────────────────────────────
class DaangnCrawler:
    def __init__(
        self,
        use_proxy:  bool  = True,
        max_workers: int  = 4,
        delay_min:  float = 1.2,
        delay_max:  float = 3.0,
        timeout:    int   = 15,
        retry:      int   = 3,
        only_010:   bool  = True,   # ← 010 번호만 수집
    ):
        self.use_proxy   = use_proxy
        self.max_workers = max_workers
        self.delay_min   = delay_min
        self.delay_max   = delay_max
        self.timeout     = timeout
        self.retry       = retry
        self.only_010    = only_010
        self._pm: Optional[ProxyManager] = None
        self._visited: set[str] = set()

    # ── 프록시 초기화 ─────────────────────────────────────
    def _init_proxy(self):
        logger.info("[Proxy] 프록시 풀 초기화 중…")
        self._pm = ProxyManager(validate=True, max_proxies=30)
        cnt = self._pm.load()
        if cnt == 0:
            logger.warning("[Proxy] 유효 프록시 없음 → 직접 연결")
            self._pm = None
        else:
            logger.info(f"[Proxy] {cnt}개 준비 완료")

    def _proxy(self) -> Optional[ProxyEntry]:
        return self._pm.get_random_proxy() if self._pm else None

    # ── HTTP GET ─────────────────────────────────────────
    def _get(self, url: str, params: dict = None) -> Optional[str]:
        for attempt in range(self.retry):
            pe = self._proxy()
            try:
                resp = requests.get(
                    url,
                    params=params,
                    headers={**DEFAULT_HEADERS, "User-Agent": random.choice(USER_AGENTS)},
                    proxies=pe.as_dict() if pe else None,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                if resp.status_code == 200:
                    if pe and self._pm: self._pm.mark_success(pe)
                    return resp.content.decode("utf-8", errors="replace")
                if resp.status_code in (403, 429):
                    if pe and self._pm: self._pm.mark_fail(pe)
                    time.sleep(random.uniform(3, 6))
            except Exception as e:
                logger.debug(f"[GET] 시도{attempt+1} 실패: {e}")
                if pe and self._pm: self._pm.mark_fail(pe)
                time.sleep(random.uniform(1, 3))
        return None

    # ── 목록 링크 수집 ────────────────────────────────────
    def _fetch_links_by_region_cat(
        self,
        region_slug: str,   # e.g. "역삼동-6035"
        category_code: str, # e.g. "FOOD_AND_BEVERAGES"
    ) -> list[str]:
        """지역+카테고리 조합으로 업체 링크 수집"""
        params: dict = {}
        if region_slug:
            params["in"] = region_slug
        if category_code:
            params["category"] = category_code
        logger.info(f"[목록] 지역={region_slug or '전체'} 카테고리={category_code or '전체'}")
        html = self._get(SEARCH_URL, params=params)
        if not html:
            return []
        links = _extract_links(html)
        logger.info(f"[목록] {len(links)}개 링크 발견")
        return links

    def _fetch_links_by_keyword(self, keyword: str) -> list[str]:
        """키워드 검색으로 업체 링크 수집"""
        logger.info(f"[검색] '{keyword}'")
        html = self._get(SEARCH_URL, params={"search": keyword})
        if not html:
            return []
        links = _extract_links(html)
        logger.info(f"[검색] '{keyword}' → {len(links)}개 링크")
        return links

    # ── 상세 페이지 파싱 ─────────────────────────────────
    def _fetch_detail(self, url: str) -> Optional[BusinessInfo]:
        if url in self._visited:
            return None
        self._visited.add(url)
        time.sleep(random.uniform(self.delay_min, self.delay_max))

        html = self._get(url)
        if not html:
            return None

        info = _parse_business(html, url)
        if not info:
            return None

        # 010 번호만 수집 옵션
        if self.only_010 and not info.has_010():
            logger.debug(f"[SKIP] 010 없음: {info.name} ({info.display_phone})")
            return None

        logger.info(f"[✓] {info.name} | {info.phone_010 or info.display_phone} | {info.address[:30]}")
        return info

    # ── 메인 실행 ────────────────────────────────────────
    def run(
        self,
        region_slug: str    = "",   # "역삼동-6035"
        category_code: str  = "",   # "FOOD_AND_BEVERAGES"
        keywords: list[str] = None,
        max_per_query: int  = 50,
        max_workers: int    = None,
    ) -> list[BusinessInfo]:

        if self.use_proxy:
            self._init_proxy()

        workers = max_workers or self.max_workers
        all_links: list[str] = []

        if region_slug or category_code:
            links = self._fetch_links_by_region_cat(region_slug, category_code)
            all_links.extend(links[:max_per_query])
        elif keywords:
            for kw in keywords:
                links = self._fetch_links_by_keyword(kw)
                all_links.extend(links[:max_per_query])
                time.sleep(random.uniform(1, 2))
        else:
            for kw in DEFAULT_KEYWORDS[:5]:
                links = self._fetch_links_by_keyword(kw)
                all_links.extend(links[:max_per_query])
                time.sleep(random.uniform(1, 2))

        # 중복 제거
        all_links = list(dict.fromkeys(all_links))
        logger.info(f"\n[크롤러] 상세 수집 대상: {len(all_links)}개\n")

        results: list[BusinessInfo] = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(self._fetch_detail, url): url for url in all_links}
            for fut in as_completed(futures):
                try:
                    info = fut.result()
                    if info:
                        results.append(info)
                except Exception as e:
                    logger.debug(f"[오류] {e}")

        logger.info(f"\n[크롤러] 완료 — {len(results)}개 수집 (010번호: {sum(1 for r in results if r.has_010())}개)")
        return results
