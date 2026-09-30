"""一条命令运行可公开复现的合成数据演示。"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from microgrid_portfolio.demo import main


if __name__ == "__main__":
    main(ROOT / "artifacts")
