"""
exporter.py
──────────────────────────────────────────────────────────
크롤링 결과를 CSV / JSON / 콘솔 출력하는 모듈.
당근마켓 크롤러 전용 – 다른 파일에 일절 영향 없음.
"""

import csv
import json
import os
import sys
from datetime import datetime
from dataclasses import asdict
from typing import List

from crawler import BusinessInfo

# Rich 사용 가능 여부 체크 (없으면 일반 출력)
try:
    from rich.table import Table
    from rich.console import Console
    from rich import box
    _RICH = True
    _console = Console()
except ImportError:
    _RICH = False


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ─── 콘솔 출력 ──────────────────────────────────────────────
def print_results(results: List[BusinessInfo], title: str = "당근마켓 동네업체 수집 결과"):
    if not results:
        print("[!] 수집된 결과가 없습니다.")
        return

    if _RICH:
        table = Table(
            title=title,
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("No", style="dim", width=4)
        table.add_column("업체명", style="bold cyan", width=20)
        table.add_column("전화번호", style="green", width=16)
        table.add_column("카테고리", style="yellow", width=12)
        table.add_column("주소", style="white", width=35)
        table.add_column("URL", style="blue", overflow="fold", width=30)

        for i, info in enumerate(results, 1):
            table.add_row(
                str(i),
                info.name[:18],
                info.display_phone(),
                info.category[:10],
                info.address[:33] if info.address else "",
                info.url.replace("https://www.daangn.com", ""),
            )
        _console.print(table)
        _console.print(f"\n[bold green]총 {len(results)}개 업체 수집 완료[/bold green]")
    else:
        print(f"\n{'='*80}")
        print(f"  {title}")
        print(f"{'='*80}")
        header = f"{'No':>4}  {'업체명':<20} {'전화번호':<16} {'카테고리':<12} {'주소':<35}"
        print(header)
        print("-" * 80)
        for i, info in enumerate(results, 1):
            print(
                f"{i:>4}  {info.name[:18]:<20} {info.display_phone():<16} "
                f"{info.category[:10]:<12} {info.address[:33] if info.address else '':<35}"
            )
        print(f"\n총 {len(results)}개 업체 수집 완료")


# ─── CSV 저장 ──────────────────────────────────────────────
def save_csv(results: List[BusinessInfo], filepath: str = None) -> str:
    if filepath is None:
        filepath = f"daangn_results_{_timestamp()}.csv"

    fieldnames = [
        "업체명", "전화번호", "안심번호", "카테고리", "주소", "지역", "설명", "URL"
    ]

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for info in results:
            writer.writerow({
                "업체명":   info.name,
                "전화번호": info.phone,
                "안심번호": info.safe_number,
                "카테고리": info.category,
                "주소":     info.address,
                "지역":     info.region,
                "설명":     info.description,
                "URL":      info.url,
            })

    abs_path = os.path.abspath(filepath)
    print(f"[✓] CSV 저장 완료: {abs_path}")
    return abs_path


# ─── JSON 저장 ─────────────────────────────────────────────
def save_json(results: List[BusinessInfo], filepath: str = None) -> str:
    if filepath is None:
        filepath = f"daangn_results_{_timestamp()}.json"

    data = []
    for info in results:
        data.append({
            "업체명":   info.name,
            "전화번호": info.phone,
            "안심번호": info.safe_number,
            "카테고리": info.category,
            "주소":     info.address,
            "지역":     info.region,
            "설명":     info.description,
            "URL":      info.url,
        })

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    abs_path = os.path.abspath(filepath)
    print(f"[✓] JSON 저장 완료: {abs_path}")
    return abs_path


# ─── 전화번호만 TXT 저장 ───────────────────────────────────
def save_phones_txt(results: List[BusinessInfo], filepath: str = None) -> str:
    if filepath is None:
        filepath = f"daangn_phones_{_timestamp()}.txt"

    phones = set()
    for info in results:
        if info.phone:
            phones.add(info.phone)
        if info.safe_number:
            phones.add(info.safe_number)

    with open(filepath, "w", encoding="utf-8") as f:
        for phone in sorted(phones):
            f.write(phone + "\n")

    abs_path = os.path.abspath(filepath)
    print(f"[✓] 전화번호 목록 저장 완료: {abs_path}  ({len(phones)}개)")
    return abs_path
