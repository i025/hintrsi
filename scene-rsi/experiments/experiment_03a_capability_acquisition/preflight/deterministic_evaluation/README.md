# Deterministic evaluation preflight

These artificial cube/floor scenes are engineering fixtures, not research reconstructions or model-generated capabilities. Four originals were checked using the actual bubblewrap namespace, existing Blender 5.2.2 and CPU-only execution. No SDK/model call occurred.

- A0: standalone source regenerated both deliverables with identical 640x360 RGBA pixels.
- A1: a deliberate external /capabilities/helper.py dependency fails source-only reproduction; the separately labeled same-condition reproduction succeeds. It is not counted as portable.
- A2: an intentional Python error produces exit code 1 and traceback, preserved without controller repair.
- A3: real saved checkpoint opens; a deliberately invalid checkpoint is recorded as a failed opening, not a missing state or success.
- Original scenes all remain unchanged and open successfully; extra +/-15 degree views execute on evaluation copies.
- Source-only execution actually confirms GT data paths and /gt are inaccessible, and /capabilities is absent.

See actual_checks.json, source_origin.json and each runs/*/analysis/technical/ record for actual commands, standard output, exceptions, scene facts and comparisons. The per-run fixture names are excluded from formal experiment runs.

Engineering issues during setup: the current tool session initially could not write the project directory, and then its network policy blocked bubblewrap creating a local NETLINK_ROUTE socket. Explicit project-write and network permissions restored the original namespace mechanism; --unshare-all was retained and no student internet access was added. A partial --run invocation initially replaced the aggregate summary with that subset; the final evaluator now aggregates all existing per-run result.json records. No formal model result was affected.

Run after every formal student has ended using the existing analysis environment:

    /srv/lab-disks/disk2/users/xymo/miniforge3/envs/scenemosaic/bin/python analysis/evaluate_capability_acquisition.py --workers 4 --same-condition

Source-only is always primary. --same-condition adds an optional separately reported external-library dependency check. --run A-T01-A0 selects a fresh unevaluated run. Existing technical output directories are retained, so this command does not silently rerun or overwrite an evaluated run. Default extra views may be disabled with --no-extra-views.
