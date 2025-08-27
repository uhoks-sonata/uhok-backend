import os
import importlib
from pathlib import Path

def get_package_size(pkg: str) -> tuple[str, float]:
    """
    패키지를 import한 뒤 설치 경로 크기를 계산한다.
    - 입력: pkg (패키지명)
    - 반환: (패키지명, 크기 MB)
    """
    try:
        mod = importlib.import_module(pkg)
        path = Path(mod.__file__).parent
        total = 0
        for root, _, files in os.walk(path):
            for f in files:
                try:
                    total += (Path(root) / f).stat().st_size
                except FileNotFoundError:
                    pass
        return pkg, total / 1024**2
    except Exception:
        return pkg, -1.0

def main():
    """
    requirements.txt 파일을 읽고 각 패키지의 설치 용량을 출력한다.
    """
    pkgs = []
    with open("requirements.txt", encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                pkgs.append(line.split("==")[0])

    print("\n[패키지 설치 용량]")
    for name in pkgs:
        pkg, size = get_package_size(name)
        if size < 0:
            print(f"{pkg:<20} 설치 확인 불가")
        else:
            print(f"{pkg:<20} {size:.2f} MB")

if __name__ == "__main__":
    main()
