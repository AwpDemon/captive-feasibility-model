# Reproducible container: regenerates every deliverable from config/assumptions.yaml.
#   docker build -f deploy/Dockerfile -t captive-feasibility .
#   docker run --rm -v "$PWD/out:/out" captive-feasibility
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY config ./config
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e .
ENTRYPOINT ["captive", "run", "--outdir", "/out", "--no-readme"]
