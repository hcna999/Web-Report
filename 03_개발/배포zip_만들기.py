# -*- coding: utf-8 -*-
"""배포/ 안의 HTML 4종을 묶어 배포용 zip을 다시 만든다.

손으로 압축하면 파일을 고친 뒤 zip을 빠뜨려 구버전이 배포된다.
(실제로 2026-08-19판 zip이 08-27판 프로그램과 8일치 어긋난 적이 있다.)
배포 폴더의 HTML을 고쳤으면 반드시 이 스크립트를 돌린다.

사용법
    python 03_개발/배포zip_만들기.py
    python 03_개발/배포zip_만들기.py --확인      # 다시 만들지 않고 최신인지 검사만
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "01_배포"
ZIP = DIST / "개폐기류_시험검사_통합패키지.zip"

# zip에 넣을 파일. 테스트 데이터는 검사자에게 갈 필요가 없으므로 넣지 않는다.
MEMBERS = [
    "개폐기류 성적서 작성프로그램.html",
    "개폐기류 품질관리 대시보드.html",
    "개폐기류 발취점검 수량표(단일규격 자동산출용).html",
    "개폐기류 발취점검 수량표(출력용).html",
]


def 검사() -> list[str]:
    """zip 내용이 실제 파일과 다른 항목의 이름을 돌려준다."""
    if not ZIP.exists():
        return list(MEMBERS)

    with zipfile.ZipFile(ZIP) as z:
        안에든것 = {i.filename: i.file_size for i in z.infolist()}

    어긋남 = []
    for name in MEMBERS:
        실제 = (DIST / name).stat().st_size
        if 안에든것.get(name) != 실제:
            어긋남.append(name)
    for name in 안에든것:
        if name not in MEMBERS:
            어긋남.append(f"{name} (zip에만 있음)")
    return 어긋남


def 만들기() -> None:
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in MEMBERS:
            src = DIST / name
            if not src.exists():
                raise FileNotFoundError(f"배포 대상이 없습니다: {src}")
            z.write(src, arcname=name)


def main() -> int:
    if not DIST.is_dir():
        print(f"배포 폴더가 없습니다: {DIST}")
        return 1

    어긋남 = 검사()

    if "--확인" in sys.argv or "--check" in sys.argv:
        if 어긋남:
            print("zip이 최신이 아닙니다:")
            for n in 어긋남:
                print(f"  - {n}")
            return 1
        print("zip이 최신입니다.")
        return 0

    만들기()
    print(f"{ZIP.name} 생성 — {len(MEMBERS)}개 파일, "
          f"{ZIP.stat().st_size / 1024 / 1024:.1f}MB")
    if 어긋남:
        print("(직전 zip과 달랐던 항목)")
        for n in 어긋남:
            print(f"  - {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
