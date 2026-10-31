"""Streamlit Community Cloud 진입점. 실제 대시보드는 src/dashboard.py 에 있습니다."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parent / "src" / "dashboard.py"), run_name="__main__")
