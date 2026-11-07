#!/system/bin/sh
# One real prompt through the binary the benchmark runs, on each backend.
cd /data/local/tmp/check || exit 1
chmod 755 litert_lm_advanced_main
for backend in cpu gpu; do
  echo "--- $backend"
  LD_LIBRARY_PATH=. ./litert_lm_advanced_main --backend="$backend" --model_path=model.litertlm \
    --input_prompt="What is the capital of France? Answer in one sentence." \
    --max_output_tokens=256 --async=false
  echo "--- $backend exit $?"
done
