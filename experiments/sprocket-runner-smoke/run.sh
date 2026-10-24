#!/usr/bin/env bash
set -euo pipefail

LLAMA_SHA="df9beac7153166550571c70cc667f270b745da49"
MODEL_REV="eb157d4ddddc4619e661d4a2426bb2dd000fc668"
MODEL_FILE="sprocket-500m-chat-q4_k_m.gguf"
MODEL_URL="https://huggingface.co/kandivault/sprocket-500m/resolve/${MODEL_REV}/${MODEL_FILE}?download=true"
ROOT="$(pwd)"
WORK="${RUNNER_TEMP:-/tmp}/sprocket-smoke"
MODEL="${WORK}/${MODEL_FILE}"
mkdir -p "${WORK}/outputs"

echo "=== runner ==="
echo "date_utc=$(date -u +%FT%TZ)"
echo "kernel=$(uname -a)"
echo "nproc=$(nproc)"
free -h || true
lscpu | sed -n '1,32p' || true
df -h "${ROOT}" || true

echo "=== fetch llama.cpp ==="
git init -q "${WORK}/llama.cpp"
git -C "${WORK}/llama.cpp" remote add origin https://github.com/ggml-org/llama.cpp.git
git -C "${WORK}/llama.cpp" fetch --depth 1 origin "${LLAMA_SHA}"
git -C "${WORK}/llama.cpp" checkout --detach FETCH_HEAD
echo "llama_sha=$(git -C "${WORK}/llama.cpp" rev-parse HEAD)"

echo "=== build llama.cpp ==="
cmake -S "${WORK}/llama.cpp" -B "${WORK}/llama.cpp/build"   -DGGML_NATIVE=OFF   -DGGML_OPENMP=ON   -DLLAMA_CURL=OFF   -DCMAKE_BUILD_TYPE=Release
cmake --build "${WORK}/llama.cpp/build" --config Release -j 4 --target llama-cli llama-bench
CLI="${WORK}/llama.cpp/build/bin/llama-cli"
BENCH="${WORK}/llama.cpp/build/bin/llama-bench"

echo "=== fetch model ==="
curl -fL --retry 3 --retry-all-errors --connect-timeout 20   -o "${MODEL}" "${MODEL_URL}"
ls -lh "${MODEL}"
sha256sum "${MODEL}"

BASE_PROMPT="$(cat experiments/sprocket-runner-smoke/prompt.txt)"
NO_PROMPT=()
if "${CLI}" --help 2>&1 | grep -q -- '--no-display-prompt'; then
  NO_PROMPT=(--no-display-prompt)
fi

echo "=== generations ==="
seeds=(101 202 303)
for idx in 0 1 2; do
  n=$((idx + 1))
  seed="${seeds[$idx]}"
  out="${WORK}/outputs/generation-${n}.txt"
  perf="${WORK}/outputs/generation-${n}.perf.txt"
  full_prompt="<|user|>${BASE_PROMPT}<|end|><|assistant|>"
  echo "--- generation ${n} seed=${seed} ---"
  start_ns=$(date +%s%N)
  "${CLI}"     -m "${MODEL}"     -p "${full_prompt}"     -n 180     -t 4     -c 2048     --temp 0.95     --top-p 0.95     --seed "${seed}"     "${NO_PROMPT[@]}"     >"${out}" 2>"${perf}"
  end_ns=$(date +%s%N)
  python3 - "${start_ns}" "${end_ns}" <<'PY'
import sys
start, end = map(int, sys.argv[1:])
print(f"wall_seconds={(end-start)/1e9:.3f}")
PY
  cat "${out}"
  echo
  grep -E 'tokens per second|eval time|prompt eval time|load time' "${perf}" || tail -n 25 "${perf}"
  echo "--- end generation ${n} ---"
done

echo "=== llama-bench best effort ==="
"${BENCH}" -m "${MODEL}" -t 4 -p 64 -n 128 -r 2 || true

echo "=== aggregate output sizes ==="
wc -c -w -l "${WORK}"/outputs/generation-*.txt
