FROM python:3.11-slim

LABEL org.opencontainers.image.title="sumsof3cubes114special"
LABEL maintainer="agbanwajamal03@gmail.com"
LABEL description="Exhaustive integer-point search: y²=x³+81t²x²+243t³x+C(n)"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Build tools + PARI/GP (optional, for curve-theory verification)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc make libgmp-dev \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir gmpy2

RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app /output \
    && chown appuser:appuser /app /output

WORKDIR /app
COPY --chown=appuser:appuser worker.c  /app/worker.c
COPY --chown=appuser:appuser Makefile  /app/Makefile
COPY --chown=appuser:appuser worker.py /app/worker.py
COPY --chown=appuser:appuser run.sh         /app/run.sh
COPY --chown=appuser:appuser healthcheck.sh /app/healthcheck.sh

# Build the fast C binary inside the image
RUN make all && chmod +x /app/run.sh /app/healthcheck.sh

VOLUME ["/output"]
USER appuser

HEALTHCHECK --interval=10m --timeout=10s --start-period=3m --retries=3 \
    CMD ["/app/healthcheck.sh"]

CMD ["/app/run.sh"]
