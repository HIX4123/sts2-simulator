#!/bin/bash
# Codespace에서 실행: sts2.dll / sts2.xml 을 /tmp/sts2-ref/에 저장
set -e
DEST=/tmp/sts2-ref
mkdir -p $DEST
git archive --remote=https://github.com/HIX4123/sts2-simulator.git _data sts2.dll sts2.xml 2>/dev/null | tar -x -C $DEST
echo "저장 위치: $DEST"
ls -lh $DEST
