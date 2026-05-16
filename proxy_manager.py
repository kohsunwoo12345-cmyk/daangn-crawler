"""
proxy_manager.py
─────────────────────────────────────────────
무료 공개 프록시를 자동 수집·검증하고 순환(Rotating) 방식으로 제공하는 모듈.
당근마켓 크롤러 전용 – 다른 파일에 일절 영향 없음.
"""

import random
import time
import logging
import requests
import threading
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# 무료 공개 프록시 소스 목록
# ──────────────────────────────────────────
PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
]

# 프록시 유효성 확인 URL (타임아웃 내 응답 여부)
TEST_URL = "https://www.google.com"
TEST_TIMEOUT = 7          # seconds
MAX_FAIL_COUNT = 3        # 연속 실패 시 블랙리스트


@dataclass
class ProxyEntry:
    host: str
    port: int
    fail_count: int = 0
    last_used: float = field(default_factory=time.time)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def as_dict(self) -> dict:
        return {"http": self.url, "https": self.url}


class ProxyManager:
    """
    사용법:
        pm = ProxyManager()
        pm.load()                 # 프록시 목록 로드 & 검증
        proxy = pm.get_proxy()    # ProxyEntry 반환
        pm.mark_fail(proxy)       # 실패 기록
        pm.mark_success(proxy)    # 성공 기록
    """

    def __init__(self, validate: bool = True, max_proxies: int = 100):
        self._lock = threading.Lock()
        self._pool: list[ProxyEntry] = []
        self._blacklist: set[str] = set()
        self._validate = validate
        self._max_proxies = max_proxies
        self._index = 0

    # ── 로드 ──────────────────────────────
    def load(self) -> int:
        """
        여러 소스에서 프록시를 가져와 (선택적으로 검증 후) 풀에 저장.
        Returns: 유효한 프록시 수
        """
        raw: set[str] = set()
        for url in PROXY_SOURCES:
            raw |= self._fetch_list(url)

        logger.info(f"[ProxyManager] 총 {len(raw)}개 프록시 수집")

        entries: list[ProxyEntry] = []
        for item in list(raw)[:300]:          # 최대 300개만 처리
            parts = item.strip().split(":")
            if len(parts) != 2:
                continue
            try:
                host, port_str = parts
                port = int(port_str)
                entries.append(ProxyEntry(host=host, port=port))
            except ValueError:
                continue

        if self._validate:
            logger.info("[ProxyManager] 프록시 유효성 검사 중 (최대 60초)…")
            valid = self._bulk_validate(entries, limit=self._max_proxies)
        else:
            valid = entries[: self._max_proxies]

        with self._lock:
            self._pool = valid
            self._index = 0

        logger.info(f"[ProxyManager] 유효 프록시 {len(self._pool)}개 준비 완료")
        return len(self._pool)

    # ── 사용 ──────────────────────────────
    def get_proxy(self) -> Optional[ProxyEntry]:
        """라운드-로빈 방식으로 프록시 반환."""
        with self._lock:
            if not self._pool:
                return None
            entry = self._pool[self._index % len(self._pool)]
            self._index += 1
            return entry

    def get_random_proxy(self) -> Optional[ProxyEntry]:
        """랜덤 프록시 반환."""
        with self._lock:
            if not self._pool:
                return None
            return random.choice(self._pool)

    def mark_fail(self, entry: ProxyEntry):
        with self._lock:
            entry.fail_count += 1
            if entry.fail_count >= MAX_FAIL_COUNT:
                self._blacklist.add(entry.url)
                if entry in self._pool:
                    self._pool.remove(entry)
                logger.debug(f"[ProxyManager] 블랙리스트 추가: {entry.url}")

    def mark_success(self, entry: ProxyEntry):
        with self._lock:
            entry.fail_count = 0
            entry.last_used = time.time()

    @property
    def count(self) -> int:
        return len(self._pool)

    # ── 내부 헬퍼 ─────────────────────────
    @staticmethod
    def _fetch_list(url: str) -> set[str]:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                lines = resp.text.strip().splitlines()
                return {ln.strip() for ln in lines if ln.strip()}
        except Exception as e:
            logger.debug(f"[ProxyManager] 소스 조회 실패 ({url}): {e}")
        return set()

    @staticmethod
    def _test_proxy(entry: ProxyEntry) -> bool:
        try:
            r = requests.get(
                TEST_URL,
                proxies=entry.as_dict(),
                timeout=TEST_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            return r.status_code < 400
        except Exception:
            return False

    def _bulk_validate(
        self, entries: list[ProxyEntry], limit: int
    ) -> list[ProxyEntry]:
        """스레드풀로 병렬 검증."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        valid: list[ProxyEntry] = []
        with ThreadPoolExecutor(max_workers=30) as ex:
            futures = {ex.submit(self._test_proxy, e): e for e in entries}
            for fut in as_completed(futures):
                e = futures[fut]
                try:
                    if fut.result():
                        valid.append(e)
                        logger.debug(f"[ProxyManager] 검증 OK: {e.url}")
                        if len(valid) >= limit:
                            break
                except Exception:
                    pass
        return valid


# ── 직접 실행 시 간단 테스트 ──────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    pm = ProxyManager(validate=True, max_proxies=10)
    cnt = pm.load()
    print(f"\n사용 가능한 프록시 수: {cnt}")
    for _ in range(min(3, cnt)):
        p = pm.get_proxy()
        if p:
            print(f"  → {p.url}")
