---
pretty_name: IDEAL
license: cc-by-4.0
language:
- en
task_categories:
- image-to-text
- object-detection
tags:
- 3d
- indoor-scenes
- blender
- layout-reasoning
size_categories:
- 1K<n<10K
configs:
- config_name: gt
  data_files:
  - split: train
    path: "**/GT.json"
---

# IDEAL-Bench: Indoor Dataset for Evaluating Analysis by 3D Layout Reasoning

> **IDEAL-Bench** is an evaluation suite that requires VLMs to predict structured 3D layouts on photorealistic indoor scenes across 10 room types, scored along five numerical dimensions (scene validity, physical plausibility, geometric accuracy, object recognition, and grid layout) and a perceptual render-and-compare protocol.
>
> Built on **IDEAL-Scenes** - 1,000 procedurally generated, re-renderable Blender scenes across 10 indoor room types, with programmatically extracted ground-truth layouts.

## Links

- Benchmark Homepage: https://ideal3d.github.io/
- Benchmark codebase: https://github.com/ideal3d/IDEAL-Bench

## Dataset Summary

- Total scenes: 1,000
- Room types: 10
- Approximate size: ~56 GB
- Data organization: one folder per scene under each room type

Room types included:

- bathroom
- bedroom
- classroom
- diningroom
- homestudio
- kitchen
- library
- livingroom
- meetingroom
- office

## File Structure

Directory layout:

```text
<root>/<room_type>/<scene_id>/
```

Typical files per scene:

- scene.blend: Blender source scene
- GT.json: structured ground-truth 3D layout annotation
- objects_in_view.json: in-view object subset
- metadata.json: camera and rendering metadata
- color.png: reference RGB render
- instance_segmentation.png: instance-level segmentation map

## Citation

```bibtex
@inproceedings{ideal2026bench,
	title     = {{IDEAL}-Bench: Indoor Dataset for Evaluating Analysis by 3D Layout Reasoning},
	author    = {Anonymous},
	booktitle = {Advances in Neural Information Processing Systems (NeurIPS)},
	year      = {2026}
}
```

## Acknowledgement

Built on [Infinigen](https://github.com/princeton-vl/infinigen) for procedural scene generation and [Blender](https://www.blender.org/) for rendering.
