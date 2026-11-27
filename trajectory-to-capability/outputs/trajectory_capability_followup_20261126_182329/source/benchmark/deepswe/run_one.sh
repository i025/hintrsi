
# bash run_deepswe.sh \
#   --model_name Qwen3.6-35B-A3B \
#   --api_base http://hubrouter.jd.com \
#   --api_key <YOUR_API_KEY> \
#   --world_size 1 \
#   --node_rank 0 \
#   --run_name lisen_rollout_test_1019 \
#   --cc_run_dir /mnt/joyai/lisen.173/cc-run/ \
#   --output_base /mnt/joyai/lisen.173/cc-run/deepswe-output \
#   --parquet_file /mnt/joyai/lisen.173/cc-run/deep_swe_tasks.parquet



bash benchmark/deepswe/run_one_loop.sh \
  --instance_id go-genai-streamed-function-args \
  --run_name lisen_loop_test \
  --max_turns 1
