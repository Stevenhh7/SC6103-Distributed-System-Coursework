"""从仓库根目录运行 python -m client；导入包本身不会启动网络。"""

from .client import main

if __name__ == "__main__":
    raise SystemExit(main())
