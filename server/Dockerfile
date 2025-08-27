FROM python:3.9.7-slim
# COPY server /
COPY server/common /common
COPY server/tests/ /tests/
COPY server/main.py /main.py

RUN python -m unittest tests/test_common.py
ENTRYPOINT ["/bin/sh"]
