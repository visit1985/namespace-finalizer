FROM python:3-alpine as base

WORKDIR /usr/src/app

FROM base as builder
COPY src/requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt

FROM base
COPY --from=builder /usr/local /usr/local
COPY src .

CMD [ "python", "./namespace_finalizer.py" ]
