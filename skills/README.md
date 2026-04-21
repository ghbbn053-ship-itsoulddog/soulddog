# Skills 目录说明

本目录用于存放用户上传或系统内置的 Skill YAML。

结构：
- `skills/<username>/*.yaml`：按用户隔离

Skill 最小规范：
```yaml
name: sample_skill
version: 1.0.0
description: 示例技能
tools:
  - name: query_schedule
    description: 查询课表
enabled: true
```

