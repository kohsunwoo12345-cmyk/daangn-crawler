"""
server.py — 당근마켓 크롤러 Web UI 백엔드 (Flask)
  · 지역(시도→구군→동) + 카테고리 선택
  · 010 번호 우선 추출
  · 엑셀(xlsx) / CSV / JSON / 전화번호 TXT 다운로드
"""

import os, sys, json, time, threading, uuid, re, csv, io
from datetime import datetime
from flask import Flask, Response, request, jsonify, send_from_directory
from flask_cors import CORS
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from crawler import DaangnCrawler, CATEGORIES, BusinessInfo
from regions import REGIONS, get_region_slug

app = Flask(__name__, static_folder=os.path.join(_DIR, "static"))
CORS(app)

# ── 작업 저장소 ─────────────────────────────────────────
jobs: dict = {}
jobs_lock  = threading.Lock()

def new_job(jid, cfg):
    with jobs_lock:
        jobs[jid] = {"id": jid, "status": "running", "config": cfg,
                     "logs": [], "results": [], "started_at": datetime.now().isoformat(), "finished_at": None}

def push_log(jid, msg):
    with jobs_lock:
        if jid in jobs: jobs[jid]["logs"].append(msg)

def push_result(jid, info: BusinessInfo):
    with jobs_lock:
        if jid in jobs:
            jobs[jid]["results"].append({
                "name": info.name,
                "phone_010": info.phone_010,
                "phone": info.phone,
                "safe_number": info.safe_number,
                "display_phone": info.display_phone,
                "category": info.category,
                "address": info.address,
                "region": info.region,
                "description": info.description,
                "url": info.url,
            })

def finish_job(jid, status="done"):
    with jobs_lock:
        if jid in jobs:
            jobs[jid]["status"] = status
            jobs[jid]["finished_at"] = datetime.now().isoformat()

# ── 로그 핸들러 ─────────────────────────────────────────
import logging

class JobLogHandler(logging.Handler):
    def __init__(self, jid):
        super().__init__()
        self.jid = jid
    def emit(self, record):
        msg = self.format(record)
        if any(x in msg for x in ["werkzeug","HTTP/1","GET /","POST /"]): return
        push_log(self.jid, msg)

# ── 크롤링 스레드 ───────────────────────────────────────
def run_crawl(jid, cfg):
    logger = logging.getLogger("daangn_crawler")
    h = JobLogHandler(jid)
    h.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
    logger.addHandler(h)
    try:
        region_slug   = cfg.get("region_slug", "")
        category_code = cfg.get("category_code", "")
        keywords      = cfg.get("keywords") or None
        use_proxy     = cfg.get("use_proxy", False)
        max_n         = int(cfg.get("max_n", 50))
        workers       = int(cfg.get("workers", 4))
        only_010      = cfg.get("only_010", True)

        sido   = cfg.get("sido","")
        sigungu= cfg.get("sigungu","")
        dong   = cfg.get("dong","")
        cat_name= cfg.get("category_name","")

        push_log(jid, f"[시작] {sido} {sigungu} {dong} | 카테고리: {cat_name} | 010전용: {only_010}")

        crawler = DaangnCrawler(
            use_proxy=use_proxy, max_workers=workers,
            delay_min=1.0, delay_max=2.5,
            timeout=15, retry=3, only_010=only_010,
        )

        # 결과 실시간 push 훅
        _orig = crawler._fetch_detail
        def _hook(url):
            info = _orig(url)
            if info: push_result(jid, info)
            return info
        crawler._fetch_detail = _hook

        results = crawler.run(
            region_slug=region_slug,
            category_code=category_code,
            keywords=keywords,
            max_per_query=max_n,
            max_workers=workers,
        )
        push_log(jid, f"[완료] {len(results)}개 수집 완료")
        finish_job(jid, "done")
    except Exception as e:
        push_log(jid, f"[오류] {e}")
        finish_job(jid, "error")
    finally:
        logger.removeHandler(h)

# ── API ─────────────────────────────────────────────────

@app.route("/api/regions")
def api_regions():
    """시도 → 구군 → 동네 트리 반환"""
    result = {}
    for sido, gungu_map in REGIONS.items():
        result[sido] = {}
        for sigungu, dongs in gungu_map.items():
            result[sido][sigungu] = [{"name": n, "id": i, "slug": get_region_slug(n,i)} for n,i in dongs]
    return jsonify(result)

@app.route("/api/categories")
def api_categories():
    return jsonify([{"name": k, "code": v} for k, v in CATEGORIES.items()])

@app.route("/api/crawl", methods=["POST"])
def api_crawl():
    data = request.json or {}
    jid  = str(uuid.uuid4())[:8]
    new_job(jid, data)
    threading.Thread(target=run_crawl, args=(jid, data), daemon=True).start()
    return jsonify({"job_id": jid})

@app.route("/api/job/<jid>")
def api_job(jid):
    with jobs_lock:
        job = jobs.get(jid)
    if not job: return jsonify({"error": "not found"}), 404
    return jsonify(job)

@app.route("/api/stream/<jid>")
def api_stream(jid):
    def generate():
        sl, sr = 0, 0
        while True:
            with jobs_lock:
                job = jobs.get(jid)
            if not job:
                yield 'data: {"error":"not found"}\n\n'; break
            for msg in job["logs"][sl:]:
                yield f'data: {json.dumps({"type":"log","msg":msg}, ensure_ascii=False)}\n\n'
                sl += 1
            for r in job["results"][sr:]:
                yield f'data: {json.dumps({"type":"result","data":r}, ensure_ascii=False)}\n\n'
                sr += 1
            if job["status"] in ("done","error"):
                yield f'data: {json.dumps({"type":"done","status":job["status"],"total":len(job["results"])}, ensure_ascii=False)}\n\n'
                break
            time.sleep(0.4)
    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

# ── 엑셀 다운로드 ────────────────────────────────────────
@app.route("/api/download/<jid>/xlsx")
def download_xlsx(jid):
    with jobs_lock:
        job = jobs.get(jid)
    if not job: return "not found", 404

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "당근마켓 동네업체"

    # 헤더 스타일
    orange  = "FFFF6F0F"
    white   = "FFFFFFFF"
    gray_bg = "FFF5F5F5"
    hdr_font = Font(name="맑은 고딕", bold=True, color=white, size=11)
    hdr_fill = PatternFill("solid", fgColor=orange)
    hdr_align= Alignment(horizontal="center", vertical="center")

    thin = Side(style="thin", color="FFDDDDDD")
    cell_border = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = ["No","업체명","010번호","전화번호(전체)","안심번호","카테고리","지역","주소","당근마켓 URL"]
    col_widths = [5, 22, 16, 18, 18, 14, 20, 40, 50]

    ws.row_dimensions[1].height = 28
    for ci, (h, w) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=1, column=ci, value=h)
        cell.font   = hdr_font
        cell.fill   = hdr_fill
        cell.alignment = hdr_align
        cell.border = cell_border
        ws.column_dimensions[get_column_letter(ci)].width = w

    # 데이터 행
    data_font  = Font(name="맑은 고딕", size=10)
    phone_font = Font(name="Courier New", size=10, bold=True, color="FFE55C00")
    center_align = Alignment(horizontal="center", vertical="center")
    left_align   = Alignment(horizontal="left",   vertical="center", wrap_text=True)

    for ri, r in enumerate(job["results"], 2):
        ws.row_dimensions[ri].height = 20
        row_fill = PatternFill("solid", fgColor=gray_bg) if ri % 2 == 0 else PatternFill("solid", fgColor="FFFFFFFF")

        values = [
            ri - 1,
            r["name"],
            r["phone_010"],
            r["phone"],
            r["safe_number"],
            r["category"],
            r["region"],
            r["address"],
            r["url"],
        ]
        for ci, val in enumerate(values, 1):
            cell = ws.cell(row=ri, column=ci, value=val)
            cell.fill   = row_fill
            cell.border = cell_border
            if ci in (3, 4, 5):   # 번호 열
                cell.font      = phone_font
                cell.alignment = center_align
            elif ci == 1:
                cell.font      = Font(name="맑은 고딕", size=10, color="FF999999")
                cell.alignment = center_align
            else:
                cell.font      = data_font
                cell.alignment = left_align

    # 자동 필터
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    ws.freeze_panes    = "A2"

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(out.read(),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=daangn_{ts}.xlsx"})

# CSV
@app.route("/api/download/<jid>/csv")
def download_csv(jid):
    with jobs_lock:
        job = jobs.get(jid)
    if not job: return "not found", 404
    si = io.StringIO(); si.write("\ufeff")
    w  = csv.DictWriter(si, fieldnames=["업체명","010번호","전화번호","안심번호","카테고리","지역","주소","URL"])
    w.writeheader()
    for r in job["results"]:
        w.writerow({"업체명":r["name"],"010번호":r["phone_010"],"전화번호":r["phone"],
                    "안심번호":r["safe_number"],"카테고리":r["category"],
                    "지역":r["region"],"주소":r["address"],"URL":r["url"]})
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(si.getvalue(), mimetype="text/csv; charset=utf-8-sig",
                    headers={"Content-Disposition": f"attachment; filename=daangn_{ts}.csv"})

# 전화번호 TXT
@app.route("/api/download/<jid>/phones")
def download_phones(jid):
    with jobs_lock:
        job = jobs.get(jid)
    if not job: return "not found", 404
    phones = sorted({r["phone_010"] for r in job["results"] if r["phone_010"]})
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response("\n".join(phones), mimetype="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=daangn_010_{ts}.txt"})

# SPA
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    sd = os.path.join(_DIR, "static")
    if path and os.path.exists(os.path.join(sd, path)):
        return send_from_directory(sd, path)
    return send_from_directory(sd, "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7979))
    print("\n" + "="*52)
    print("  🥕 당근마켓 동네업체 크롤러 - Web UI")
    print(f"  http://0.0.0.0:{port}")
    print("="*52 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
