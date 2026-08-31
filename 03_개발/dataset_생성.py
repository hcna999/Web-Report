# -*- coding: utf-8 -*-
"""품질관리 대시보드 검증용 성적서 XML 100세트 생성 (로컬 전용).

성적서 작성 프로그램을 헤드리스 브라우저로 띄운 뒤, 그 프로그램의
buildQIR() / qirToXML() 을 그대로 호출해 XML을 만든다. 손으로 XML을 짜면
스키마가 어긋나므로 반드시 앱이 직접 만들게 한다.

  python 03_개발/dataset_생성.py [출력폴더] [세트수]

기본 출력: 03_개발/테스트데이터/dataset_100_sets  (git 추적 제외)
"""
from __future__ import annotations

import random
import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
APP = ROOT / "01_배포" / "개폐기류 성적서 작성프로그램.html"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "03_개발" / "테스트데이터" / "dataset_100_sets"
TOTAL = int(sys.argv[2]) if len(sys.argv) > 2 else 100

SEED = 20260831          # 매번 같은 데이터가 나오도록 고정
FAIL_RATE = 0.15         # 불합격 비율
INSPECTION = ["발취점검", "정기점검", "수시점검", "출하검사"]
GRADES = ["S", "A", "B", "B", "B", "C", "D"]      # B가 많은 실제 분포에 가깝게
INSPECTORS = ["박민수", "김도현", "이수진", "정한결", "최윤호"]
TESTERS = ["오승우", "한지훈", "서예린", "문상혁", "배주원"]

# 앱 안에서 한 건을 만들고 XML을 돌려주는 스크립트.
# STATE 를 항목 종류별로 채워 itemJudged() 가 판정을 내도록 한다.
JS = r"""
(cfg) => {
  const spec = SPECS.find(s => s.id === cfg.specId);
  if (!spec) throw new Error('규격 없음: ' + cfg.specId);
  startInspection(spec);

  const v = spec.variants[cfg.variantIdx % spec.variants.length];
  CUR.variant = v.value; CUR.mode = v.mode;
  CUR.grade = cfg.grade; CUR.gradeSource = '검사자 선택';

  const serials = Array.from({length: cfg.qty}, (_, i) => 'SN-' + String(i + 1).padStart(3, '0'));
  Object.assign(STATE.__base, {
    lot: cfg.lot, qty: cfg.qty, maker: cfg.maker, itype: cfg.itype,
    sdate: cfg.sdate, edate: cfg.edate, insp: cfg.insp, test: cfg.test,
    serialsInput: serials.join(', ')
  });

  // 불합격으로 만들 항목 하나를 고르기 위해 대상 목록을 모은다
  const targets = [];
  spec.steps.forEach(sd => (sd.items || []).forEach(it => targets.push(it)));
  const failIt = cfg.fail ? targets[cfg.failIdx % targets.length] : null;

  spec.steps.forEach(sd => (sd.items || []).forEach(it => {
    const bad = failIt && it.key === failIt.key;
    if (it.full) {
      STATE[it.key] = { full: { jdg: bad ? '불량' : '양호', badSerials: bad ? [serials[0]] : [] } };
      return;
    }
    if (it.cert) {
      STATE[it.key] = it.docOnly
        ? { certFiles: [{ name: it.name + '_성적서.pdf' }] }
        : { cert: { submit: bad ? '미제출' : '제출' } };
      return;
    }
    const n = Math.max(1, Math.min(cfg.qty, sampCount(it) || 1));
    const picked = serials.slice(0, n);
    const res = {};
    picked.forEach((sn, i) => { res[sn] = { jdg: (bad && i === 0) ? '불량' : '양호' }; });
    STATE[it.key] = { serials: picked, res };
  }));

  STATE.__final = { remark: cfg.fail ? '※ 불합격 항목 발생 — 해당 항목 재시험 필요'
                                     : '※ 검사 및 시험 항목 전항목 적합판정' };

  const q = buildQIR();
  const items = Object.values(q.results).reduce((a, r) => a.concat(r.items), []);
  return {
    xml: qirToXML(q),
    judgement: q.final.judgement,
    material: q.material,
    items: items.length,
    unjudged: items.filter(i => !i.jdg && !i.na && !i.exempt).length
  };
}
"""


def main() -> int:
    if not APP.exists():
        print("앱을 찾을 수 없습니다:", APP)
        return 1

    rnd = random.Random(SEED)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(APP.as_uri(), wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        spec_ids = page.evaluate("SPECS.map(s => s.id)")
        makers = page.evaluate("MAKERS.map(m => (typeof m === 'string') ? m : (m.name || m.maker || ''))")
        makers = [m for m in makers if m]
        print("규격 %d종 · 제조업체 %d개" % (len(spec_ids), len(makers)))

        # 규격을 고르게 돌리되 나머지는 임의 배정
        plan = [spec_ids[i % len(spec_ids)] for i in range(TOTAL)]
        rnd.shuffle(plan)

        stats: dict[str, int] = {}
        fails = 0
        for i, sid in enumerate(plan, 1):
            fail = rnd.random() < FAIL_RATE
            day = rnd.randint(1, 28)
            cfg = {
                "specId": sid,
                "variantIdx": rnd.randrange(4),
                "grade": rnd.choice(GRADES),
                "qty": rnd.choice([5, 8, 10, 12, 15, 20, 24, 30, 33, 40, 50]),
                "lot": str(rnd.randint(480000, 499999)),
                "maker": rnd.choice(makers),
                "itype": rnd.choice(INSPECTION),
                "sdate": "2026-07-%02d" % day,
                "edate": "2026-07-%02d" % day,
                "insp": rnd.choice(INSPECTORS),
                "test": rnd.choice(TESTERS),
                "fail": fail,
                "failIdx": rnd.randrange(50),
            }
            r = page.evaluate(JS, cfg)
            if r["unjudged"]:
                print("  ! %03d %s — 판정 안 된 항목 %d개" % (i, sid, r["unjudged"]))

            jd = r["judgement"]
            fails += jd.startswith("불합격")   # 앱은 "불합격(중도종료)"로 표기
            stats[sid] = stats.get(sid, 0) + 1
            safe_maker = cfg["maker"].replace("/", "_").replace("\\", "_")
            name = "Set_%03d_[%s]_%s_%s_%s_%s_%s.xml" % (
                i, jd, cfg["itype"], safe_maker,
                cfg["sdate"].replace("-", ""), cfg["lot"], sid)
            (OUT / name).write_text(r["xml"], encoding="utf-8")

        browser.close()

    print("\n생성 완료 — %s" % OUT)
    print("  총 %d건 (불합격 %d건, %.0f%%)" % (TOTAL, fails, fails / TOTAL * 100))
    for k in sorted(stats):
        print("  %-7s %d건" % (k, stats[k]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
