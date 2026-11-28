# Experiment 03 deterministic data preparation

The split was chosen before any new student outcome. Three unused local candidates were reused and their missing Blender files downloaded. Four first-listed scene IDs from new categories were obtained from the official dataset API. No whole dataset, environment, model, or archive was downloaded.

All seven scenes opened in Blender 5.2.2 LTS with scripts disabled, with zero missing external image resources. Validation rerenders used CPU, 8 threads, affinity 56-63, nice 15, 32 GiB virtual-memory limit, 640x360 and 16 Cycles samples. Original RGB is 1280x720 and the original sample budget is preserved in full_state.json; rerenders are checks of gross agreement, not pixel-identical reproductions.

| Scene | Role | Visible objects | Blender objects | MAE | Auxiliary SSIM |
| --- | --- | ---: | ---: | ---: | ---: |
| A-T01 office/office_s1210607562 | test_a | 21 | 95 | 0.01568 | 0.9422 |
| A-T02 bedroom/bedroom_s1379154151 | test_a | 8 | 51 | 0.02508 | 0.9383 |
| A-T03 kitchen/kitchen_s1256694276 | test_a | 7 | 44 | 0.01661 | 0.9033 |
| A-T04 livingroom/livingroom_s1399412440 | test_a | 9 | 47 | 0.01918 | 0.8841 |
| A-S01 diningroom/diningroom_s1627438743 | selection_a | 8 | 45 | 0.02184 | 0.9152 |
| B-T01 classroom/classroom_s1476231586 | test_b | 19 | 68 | 0.01289 | 0.9450 |
| B-T02 meetingroom/meetingroom_s1487880933 | test_b | 14 | 60 | 0.01261 | 0.9368 |

The development technical package at development_gt/ extracts actual material trees, complete node-group trees, sockets, links, object material polygon bindings, UV layer ranges and samples, hierarchy, transform matrices, camera, lights, external-image status and bounding-box projections. Segmentation statistics are computed from the provided image and metadata ID map. No geometry, semantic-facing rule, hidden surface, original construction program, or technical diagnosis is inferred by this deterministic extractor.

The development Blender assets remain at original paths; no GT asset is copied into any student capability library. New test and selection GT are stored separately under data/experiment_03/evaluation_gt. Student tasks must copy only anonymous reference RGB.

Source and license: [IDEAL-Scenes](https://huggingface.co/datasets/IDEAL-Benchmark/IDEAL-Scenes), CC-BY-4.0. The frozen_split.json, original source.json records and per-scene source_file_listing.json preserve actual origin and file sizes without calculating hashes.

Engineering record: the SDK environment did not contain Pillow and the lightweight image-to-3D environment lacked NumPy. Deterministic image statistics reused the existing miniforge3/envs/scenemosaic environment; no package or environment was modified. Actual Blender execution succeeded. Its deprecation warnings and one imported color-space enum warning are preserved in the inspection logs.
