"""
main.py
──────────────────────────────────────────────────────────
당근마켓 동네업체 전화번호 크롤러 - 진입점 (Entry Point)
──────────────────────────────────────────────────────────

사용법:
  python main.py                          # 기본 실행 (모든 기본 키워드)
  python main.py -k 카페 음식점 미용실     # 특정 키워드만
  python main.py -c CAFE_AND_BAKERY       # 카테고리 방식
  python main.py --no-proxy               # 프록시 없이 실행
  python main.py -n 20                    # 키워드당 최대 20개
  python main.py -o results               # 결과 파일 접두어 설정
  python main.py --list-categories        # 카테고리 목록 출력
"""

import argparse
import sys
import os

# ── 이 디렉토리만 경로 추가 (다른 파일 영향 없음) ──────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from crawler import DaangnCrawler, CATEGORIES, DEFAULT_KEYWORDS
from exporter import print_results, save_csv, save_json, save_phones_txt


def parse_args():
    parser = argparse.ArgumentParser(
        description="당근마켓 동네업체 전화번호 크롤러 (프록시 로테이션)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python main.py
  python main.py -k 카페 음식점
  python main.py -c CAFE_AND_BAKERY FOOD_AND_BEVERAGES
  python main.py --no-proxy -n 50 -w 3
  python main.py --list-categories
        """,
    )

    parser.add_argument(
        "-k", "--keywords",
        nargs="+",
        default=None,
        metavar="KEYWORD",
        help="검색할 키워드 목록 (예: 카페 음식점 미용실)"
    )
    parser.add_argument(
        "-c", "--categories",
        nargs="+",
        default=None,
        metavar="CATEGORY",
        help="카테고리 코드 목록 (--list-categories 로 확인)"
    )
    parser.add_argument(
        "-n", "--max-per-keyword",
        type=int,
        default=30,
        metavar="N",
        help="키워드/카테고리당 최대 수집 업체 수 (기본: 30)"
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=3,
        metavar="N",
        help="병렬 워커 수 (기본: 3, 과부하 방지를 위해 5 이하 권장)"
    )
    parser.add_argument(
        "--no-proxy",
        action="store_true",
        help="프록시 없이 직접 연결"
    )
    parser.add_argument(
        "--delay-min",
        type=float,
        default=1.5,
        metavar="SEC",
        help="요청 간 최소 딜레이 초 (기본: 1.5)"
    )
    parser.add_argument(
        "--delay-max",
        type=float,
        default=3.5,
        metavar="SEC",
        help="요청 간 최대 딜레이 초 (기본: 3.5)"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        metavar="PREFIX",
        help="출력 파일 접두어 (기본: daangn_results_TIMESTAMP)"
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json", "both", "phones"],
        default="both",
        help="출력 형식 (기본: both=CSV+JSON)"
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="사용 가능한 카테고리 목록 출력 후 종료"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="상세 로그 출력"
    )

    return parser.parse_args()


def list_categories():
    print("\n[ 당근마켓 동네업체 카테고리 목록 ]")
    print("-" * 45)
    print(f"  {'카테고리 이름':<15} {'코드'}")
    print("-" * 45)
    for name, code in CATEGORIES.items():
        print(f"  {name:<15} {code or '(전체 - 코드 없음)'}")
    print("-" * 45)
    print("\n사용 예: python main.py -c CAFE_AND_BAKERY FOOD_AND_BEVERAGES\n")


def main():
    args = parse_args()

    if args.list_categories:
        list_categories()
        sys.exit(0)

    # 로그 레벨 설정
    if args.verbose:
        import logging
        logging.getLogger("daangn_crawler").setLevel(logging.DEBUG)
        logging.getLogger("ProxyManager").setLevel(logging.DEBUG)

    print("\n" + "=" * 60)
    print("  당근마켓 동네업체 전화번호 크롤러")
    print("=" * 60)
    print(f"  프록시 사용: {'아니오' if args.no_proxy else '예 (자동 수집·검증)'}")
    print(f"  병렬 워커:   {args.workers}")
    print(f"  요청 딜레이: {args.delay_min}~{args.delay_max}초")
    print(f"  최대 수집:   키워드당 {args.max_per_keyword}개")
    if args.keywords:
        print(f"  키워드:      {', '.join(args.keywords)}")
    elif args.categories:
        print(f"  카테고리:    {', '.join(args.categories)}")
    else:
        print(f"  키워드:      기본값 {len(DEFAULT_KEYWORDS)}개")
    print("=" * 60 + "\n")

    # ── 크롤러 초기화 ──────────────────────────────────
    crawler = DaangnCrawler(
        use_proxy=not args.no_proxy,
        max_workers=args.workers,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        timeout=15,
        retry=3,
    )

    # ── 실행 ───────────────────────────────────────────
    results = crawler.run(
        keywords=args.keywords,
        categories=args.categories,
        max_detail_per_kw=args.max_per_keyword,
        max_workers=args.workers,
    )

    # ── 결과 출력 ──────────────────────────────────────
    print_results(results)

    if not results:
        print("\n[!] 수집된 결과가 없습니다. 키워드나 옵션을 변경해 재시도하세요.")
        sys.exit(1)

    # ── 파일 저장 ──────────────────────────────────────
    # 결과 저장 디렉토리 = 현재 스크립트 위치
    os.chdir(_THIS_DIR)

    prefix = args.output
    fmt = args.format

    if fmt in ("csv", "both"):
        csv_path = f"{prefix}.csv" if prefix else None
        save_csv(results, csv_path)

    if fmt in ("json", "both"):
        json_path = f"{prefix}.json" if prefix else None
        save_json(results, json_path)

    if fmt == "phones":
        txt_path = f"{prefix}_phones.txt" if prefix else None
        save_phones_txt(results, txt_path)

    # 전화번호 목록은 항상 추가 저장
    phones_path = f"{prefix}_phones.txt" if prefix else None
    save_phones_txt(results, phones_path)

    print("\n[완료] 모든 결과가 저장되었습니다.")


if __name__ == "__main__":
    main()
