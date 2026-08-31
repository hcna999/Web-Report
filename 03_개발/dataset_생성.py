# -*- coding: utf-8 -*-
"""품질관리 대시보드 검증용 성적서 XML 데이터셋 생성 (로컬 전용).

성적서 작성 프로그램을 헤드리스 브라우저로 띄운 뒤, 그 프로그램의
buildQIR() / qirToXML() 을 그대로 호출해 XML을 만든다. 손으로 XML을 짜면
스키마가 어긋나므로 반드시 앱이 직접 만들게 한다.

대시보드가 의미 있는 그림을 그리려면 데이터에 편차가 있어야 하므로
  · 업체마다 품질 성향(우수/보통/주의)을 부여해 불합격률·품질등급을 다르게
  · 불량 건은 항목 수(1~3개)와 제조번호 수(1~2대)를 달리
  · 부분방전·기밀·도장·상연결 접속재는 실측값을 넣어 위험점수가 갈리도록
했다.

  python 03_개발/dataset_생성.py [출력폴더] [세트수]

기본 출력: 03_개발/테스트데이터/dataset_500_sets  (git 추적 제외)
"""
from __future__ import annotations

import random
import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "01_배포" / "개폐기류 성적서 작성프로그램.html"
TOTAL = int(sys.argv[2]) if len(sys.argv) > 2 else 500
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "03_개발" / "테스트데이터" / "dataset_500_sets"

SEED = 20260831

# 업체 성향 — 실제로도 업체별 편차가 크다. 비율은 (전체업체 대비) 대략적인 분포.
#   tier: (불합격 확률, 등급 가중치, 여유부족 두께가 나올 확률)
TIERS = {
    "우수": (0.015, ["S", "S", "A", "A", "B"],           0.04),
    "보통": (0.055, ["A", "B", "B", "B", "B", "C"],       0.12),
    "주의": (0.150, ["B", "C", "C", "D", "D"],           0.30),
}
TIER_MIX = ["우수"] * 3 + ["보통"] * 5 + ["주의"] * 2   # 업체 10곳당 우수3·보통5·주의2

INSPECTION = ["발취점검", "정기점검", "수시점검", "출하검사"]
INSPECTORS = ["박민수", "김도현", "이수진", "정한결", "최윤호", "임재원"]
TESTERS = ["오승우", "한지훈", "서예린", "문상혁", "배주원", "노가영"]

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

  const all = [];
  spec.steps.forEach(sd => (sd.items || []).forEach(it => all.push(it)));
  // 불량으로 만들 항목 (판정이 실제로 뒤집히는 종류만 고른다)
  const badKeys = new Set(
    (cfg.badPicks || []).map(i => all[i % all.length]).map(it => it.key));

  const R = (() => { let s = cfg.seed >>> 0;
    return () => (s = (s * 1664525 + 1013904223) >>> 0) / 4294967296; })();
  const between = (a, b) => a + (b - a) * R();

  spec.steps.forEach(sd => (sd.items || []).forEach(it => {
    const bad = badKeys.has(it.key);

    if (it.full) {
      STATE[it.key] = { full: { jdg: bad ? '불량' : '양호',
                                badSerials: bad ? [serials[0]] : [] } };
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
    const nBad = bad ? Math.min(picked.length, cfg.badSerialCount) : 0;
    const res = {};

    picked.forEach((sn, i) => {
      const isBad = i < nBad;

      // 상연결 접속재 — 9칸 실측(기준 12mm 이상). 여유가 빠듯한 로트를 섞는다
      if (it.phaseConn) {
        const base = isBad ? between(10.4, 11.8)
                   : (cfg.tightConn ? between(12.1, 13.8) : between(14.5, 18.0));
        const f = {}; let min = Infinity;
        ['A', 'B', 'C'].forEach(ph => [1, 2, 3].forEach(k => {
          const val = Number((base + between(0, 1.2)).toFixed(1));
          f['pc_' + ph + k] = String(val);
          if (val < min) min = val;
        }));
        // 9칸 값과 별개로 판정도 넣어야 itemJudged()가 항목을 판정된 것으로 본다
        res[sn] = { fields: f, jdg: min >= it.thr.v ? '양호' : '불량' };
        return;
      }

      // 도장·부분방전(상별)·최소동작전류·T-C·Sequence·저항은 입력칸 구조가
      // 따로 있어 단일 실측값으로는 판정되지 않는다. 판정만 직접 넣는다.
      if (it.paintTest || it.pdPhase || it.minTrip || it.tcTest || it.seqTest || it.resistance) {
        res[sn] = { jdg: isBad ? '불량' : '양호' };
        return;
      }

      // 단일 임계값 항목 — 실측값을 넣으면 앱이 자동판정한다
      if (it.thr) {
        const t = it.thr.v, le = it.thr.dir === 'le';
        const val = le ? (isBad ? between(t * 1.05, t * 1.6) : between(t * 0.25, t * 0.85))
                       : (isBad ? between(t * 0.6, t * 0.95) : between(t * 1.05, t * 1.5));
        res[sn] = { val: val.toFixed(t < 5 ? 2 : 1) };
        return;
      }

      res[sn] = { jdg: isBad ? '불량' : '양호' };
    });

    STATE[it.key] = { serials: picked, res };
  }));

  STATE.__final = { remark: badKeys.size
      ? '※ 불합격 항목 발생 — 해당 항목 재시험 필요'
      : '※ 검사 및 시험 항목 전항목 적합판정' };

  const q = buildQIR();
  const items = Object.values(q.results).reduce((a, r) => a.concat(r.items), []);
  return {
    xml: qirToXML(q),
    judgement: q.final.judgement,
    badNames: items.filter(i => i.jdg === '불량').map(i => i.name),
    unjudged: items.filter(i => !i.jdg && !i.na && !i.exempt).map(i => i.name + '/' + i.kind)
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
        makers = [m for m in page.evaluate(
            "MAKERS.map(m => (typeof m === 'string') ? m : (m.name || m.maker || ''))") if m]

        # 업체마다 성향을 고정 배정 (매번 같은 업체가 같은 성향이어야 추세가 읽힌다)
        tier_of = {m: TIER_MIX[i % len(TIER_MIX)] for i, m in enumerate(sorted(makers))}
        print("규격 %d종 · 제조업체 %d개 (우수 %d · 보통 %d · 주의 %d)" % (
            len(spec_ids), len(makers),
            *[sum(1 for t in tier_of.values() if t == k) for k in ("우수", "보통", "주의")]))

        plan = [spec_ids[i % len(spec_ids)] for i in range(TOTAL)]
        rnd.shuffle(plan)

        by_spec: dict[str, int] = {}
        by_tier: dict[str, list[int]] = {k: [0, 0] for k in TIERS}   # [총건수, 불합격]
        bad_names: dict[str, int] = {}
        fails = 0

        for i, sid in enumerate(plan, 1):
            maker = rnd.choice(makers)
            tier = tier_of[maker]
            fail_p, grades, tight_p = TIERS[tier]
            fail = rnd.random() < fail_p
            day = rnd.randint(1, 28)
            month = rnd.choice([6, 6, 7, 7, 7, 8])
            cfg = {
                "specId": sid,
                "variantIdx": rnd.randrange(6),
                "grade": rnd.choice(grades),
                "qty": rnd.choice([5, 8, 10, 12, 15, 20, 24, 30, 33, 40, 50, 60]),
                "lot": str(rnd.randint(480000, 499999)),
                "maker": maker,
                "itype": rnd.choice(INSPECTION),
                "sdate": "2026-%02d-%02d" % (month, day),
                "edate": "2026-%02d-%02d" % (month, day),
                "insp": rnd.choice(INSPECTORS),
                "test": rnd.choice(TESTERS),
                # 불량 항목 1~3개 · 불량 제조번호 1~2대로 사례를 흩는다
                "badPicks": [rnd.randrange(60) for _ in range(rnd.choice([1, 1, 1, 2, 3]))] if fail else [],
                "badSerialCount": rnd.choice([1, 1, 2]),
                "tightConn": rnd.random() < tight_p,
                "seed": rnd.randrange(1 << 30),
            }
            r = page.evaluate(JS, cfg)
            if r["unjudged"]:
                print("  ! %04d %s — 미판정: %s" % (i, sid, ", ".join(r["unjudged"])))

            jd = r["judgement"]
            is_fail = jd.startswith("불합격")      # 앱은 "불합격(중도종료)"로 표기
            fails += is_fail
            by_spec[sid] = by_spec.get(sid, 0) + 1
            by_tier[tier][0] += 1
            by_tier[tier][1] += is_fail
            for nm in r["badNames"]:
                bad_names[nm] = bad_names.get(nm, 0) + 1

            safe = cfg["maker"].replace("/", "_").replace("\\", "_")
            (OUT / ("Set_%04d_[%s]_%s_%s_%s_%s_%s.xml" % (
                i, jd, cfg["itype"], safe, cfg["sdate"].replace("-", ""),
                cfg["lot"], sid))).write_text(r["xml"], encoding="utf-8")

            if i % 100 == 0:
                print("  ... %d/%d" % (i, TOTAL))

        browser.close()

    print("\n생성 완료 — %s" % OUT)
    print("  총 %d건 · 불합격 %d건 (%.1f%%)" % (TOTAL, fails, fails / TOTAL * 100))
    print("  업체 성향별 불합격률")
    for k, (n, f) in by_tier.items():
        print("    %-4s %4d건 중 %3d건 (%.1f%%)" % (k, n, f, f / n * 100 if n else 0))
    print("  규격별 건수: " + " · ".join("%s %d" % (k, by_spec[k]) for k in sorted(by_spec)))
    top = sorted(bad_names.items(), key=lambda kv: -kv[1])[:6]
    print("  불량이 잦은 항목: " + " · ".join("%s %d건" % (k, v) for k, v in top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
