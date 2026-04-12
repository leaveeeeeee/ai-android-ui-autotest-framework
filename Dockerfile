FROM python:3.13-slim

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY config ./config
COPY docs ./docs
COPY examples ./examples
COPY tests ./tests
COPY framework ./framework
COPY scripts ./scripts
COPY assets ./assets

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install .

CMD ["python", "-m", "pytest", "tests/test_via_baidu_search.py", "-m", "smoke and device", "--simple-html=artifacts/reports/via_baidu_report.html", "--html=artifacts/reports/via_baidu_pytest_html_report.html", "--self-contained-html", "--alluredir=artifacts/report_data/allure-results", "--clean-alluredir"]
