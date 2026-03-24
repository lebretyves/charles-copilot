FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN adduser --system --no-create-home --group appuser
USER appuser
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, time, sys; f='/tmp/sim.hb'; sys.exit(0 if os.path.exists(f) and time.time()-os.path.getmtime(f)<90 else 1)"
CMD ["python", "-m", "simulator.main"]
