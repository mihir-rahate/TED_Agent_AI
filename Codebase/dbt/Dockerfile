FROM python:3.11

ENV PYTHONUNBUFFERED=1
ENV DBT_PROFILES_DIR=/usr/app/profiles

WORKDIR /usr/app

COPY requirements.txt .

# 1) Install everything
RUN pip install --no-cache-dir -r requirements.txt \
    # 2) Then *force* protobuf 4.25.3 as the final state
    && pip uninstall -y protobuf \
    && pip install --no-cache-dir "protobuf==4.25.3"

COPY . .

ENTRYPOINT ["dbt"]
