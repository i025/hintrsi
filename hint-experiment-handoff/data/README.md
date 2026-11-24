# 外部实验输入

默认配置在这里找 `deep_swe_tasks.parquet` 和 `tasks/`。这两个输入没有装进交接包，请按 [运行指南](../docs/运行指南.md) 获取。

```text
data/
  deep_swe_tasks.parquet
  tasks/
    <instance_id>/
      task.toml
      tests/Dockerfile
      tests/test.sh
      solution/solution.patch
```

任务目录还可能包含其他构建文件，必须保留完整目录。Parquet、任务目录、镜像和 Golden Patch 要来自相互匹配的数据版本。也可以在本地配置中填入现有数据的绝对路径，无需复制到这里。
