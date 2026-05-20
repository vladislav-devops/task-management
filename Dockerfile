# the Dockerfile made by me (Vladislav Levchenko)
# using a leightweight image
FROM python:3.11-alpine AS builder
WORKDIR /build

# tools needed to compile
RUN apk add --no-cache gcc musl-dev libffi-dev

COPY requirements.txt .

# makes copying out clean in the next stage
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt \
 && find /install -depth \
      \( -name '__pycache__' -o -name 'tests' -o -name 'test' \) \
      -type d -exec rm -rf {} + \
 && find /install -name '*.pyc' -delete \
 && find /install -name '*.pyo' -delete


FROM python:3.11-alpine
# that's me, once again
LABEL author="Vladislav Levchenko"

WORKDIR /app

# copy packages from the builder
COPY --from=builder /install /usr/local

COPY app/ ./app/

# non-root user
RUN addgroup -S app && adduser -S app -G app -h /home/app \
 && chown -R app:app /app
USER app

# docker logs shows output fast; also skip .pyc files in the image
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
