FROM python:3.12.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV AICOMIC_REQUIRE_FULL_DEPENDENCY_AUDIT=1

WORKDIR /app

COPY . .

RUN mkdir -p reports state logs \
    && python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir --constraint requirements-lock.txt -e ".[web,validation,local-providers]"

ENV PYTHONPATH=/app/src:/app

CMD ["sh", "-lc", "python scripts/run_demo_validation.py && python scripts/validate_full_system_suite.py"]
