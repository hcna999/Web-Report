# -*- coding: utf-8 -*-
"""배포/ 안의 HTML을 대상별로 묶어 배포용 zip을 다시 만든다.

  · 통합패키지  : 한전 검사자용 4종
  · 제조사패키지: 제조사 자체검사용 2종 (검수 전용 항목이 없는 별도 프로그램)


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
# 대상별 zip. 테스트 데이터는 배포 대상이 아니므로 넣지 않는다.
# 제조사 프로그램은 한전 검수 전용 항목(품질등급·서명·사진·첨부)이 없는 별도 앱이므로
# 검사자용 통합패키지와 섞지 않고 따로 묶는다.
PACKAGES = {
    "개폐기류_시험검사_통합패키지.zip": [
        "개폐기류 성적서 작성프로그램.html",
        "개폐기류 품질관리 대시보드.html",
        "개폐기류 발취점검 수량표(단일규격 자동산출용).html",
        "개폐기류 발취점검 수량표(출력용).html",
    ],
    "개폐기류_제조사_자체검사패키지.zip": [
        "개폐기류 제조사 자체검사 프로그램.html",
        "개폐기류 제조사 품질 대시보드.html",
    ],
}


def 검사(zip_name: str, members: list[str]) -> list[str]:
    """zip 내용이 실제 파일과 다른 항목의 이름을 돌려준다."""
    zip_path = DIST / zip_name
    if not zip_path.exists():
        return list(members)

    with zipfile.ZipFile(zip_path) as z:
        안에든것 = {i.filename: i.file_size for i in z.infolist()}

    어긋남 = []
    for name in members:
        실제 = (DIST / name).stat().st_size
        if 안에든것.get(name) != 실제:
            어긋남.append(name)
    for name in 안에든것:
        if name not in members:
            어긋남.append(f"{name} (zip에만 있음)")
    return 어긋남


def 만들기(zip_name: str, members: list[str]) -> None:
    with zipfile.ZipFile(DIST / zip_name, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in members:
            src = DIST / name
            if not src.exists():
                raise FileNotFoundError(f"배포 대상이 없습니다: {src}")
            z.write(src, arcname=name)


def main() -> int:
    if not DIST.is_dir():
        print(f"배포 폴더가 없습니다: {DIST}")
        return 1

    확인만 = "--확인" in sys.argv or "--check" in sys.argv
    문제 = False

    for zip_name, members in PACKAGES.items():
        어긋남 = 검사(zip_name, members)

        if 확인만:
            if 어긋남:
                문제 = True
                print(f"{zip_name} 이 최신이 아닙니다:")
                for n in 어긋남:
                    print(f"  - {n}")
            else:
                print(f"{zip_name} 최신입니다.")
            continue

        만들기(zip_name, members)
        print(f"{zip_name} 생성 — {len(members)}개 파일, "
              f"{(DIST / zip_name).stat().st_size / 1024 / 1024:.1f}MB")
        if 어긋남:
            print("(직전 zip과 달랐던 항목)")
            for n in 어긋남:
                print(f"  - {n}")

    return 1 if (확인만 and 문제) else 0


if __name__ == "__main__":
    raise SystemExit(main())
