#!/usr/bin/env bash
# Chạy web app — tự activate venv, không cần nhớ activate tay mỗi lần mở terminal mới.
set -e
cd "$(dirname "$0")"

if [ ! -f "venv/bin/activate" ]; then
    echo "❌ Không tìm thấy venv. Chạy trước: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

source venv/bin/activate
python app.py
