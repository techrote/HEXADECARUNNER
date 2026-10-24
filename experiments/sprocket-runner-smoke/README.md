# Sprocket GitHub-hosted runner smoke test

This is an isolated exploratory experiment. It is not part of HEXADECARUNNER's distributed-runtime qualification and does not alter the framework.

The smoke test asks whether a standard `ubuntu-24.04` GitHub-hosted CPU runner can download and execute the 501M-parameter Sprocket chat GGUF with llama.cpp and emit several short behaviour-concept generations.

Pinned inputs:

- Model repository: `kandivault/sprocket-500m`
- Model revision: `eb157d4ddddc4619e661d4a2426bb2dd000fc668`
- Model file: `sprocket-500m-chat-q4_k_m.gguf`
- llama.cpp revision: `df9beac7153166550571c70cc667f270b745da49`
- Runner: `ubuntu-24.04`
- Inference threads: 4

The workflow records CPU/RAM metadata, model SHA-256, three short generations, llama.cpp timing output and a best-effort `llama-bench` sample.
