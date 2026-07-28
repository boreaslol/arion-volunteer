# Arion Volunteer

[English](README.md)

> **现实提供经验，反事实产生主体性。**

Arion Volunteer 是 [Arion Judgment Core](https://github.com/boreaslol/arion-core)
加上公开的八角色治理模型和通用 Skill 目录之后形成的社区版本。

它组织一个集体判断如何形成、被承担、接受质疑，并在现实反驳后继续修正。
角色保存长期责任，Agent instance 只为当前 Run 中尚未解决的问题临时生成。

## 包含什么

- 当前 Arion 的规划与执行 Core；
- 八个边界明确的治理角色；
- 十一个可复用的 `SKILL.md` 操作方法；
- 一个只读取本地生成证据的 Volunteer Pack；
- 对规划、并行 Agent、判断收口、角色资产和公开边界的测试。

## 不包含什么

- 不包含业务语义层、指标口径、来源定义、字段字典；
- 不包含账号配置、密码、token、session、私钥或其他 secret value；
- 不包含公司数据、客户数据、私有知识、内部地址和生产适配器；
- 不包含 Runtime 状态、模型、发布包，也不继承私有 Git 历史。

随仓库提供的 Pack 明确声明 `semantic_roots: []`；唯一的 Connector
只读取本地生成证据，并且没有 secret slot。

## 八个角色

| 角色 | 不可约责任 |
|---|---|
| Lead | 承担有界集体判断与收口 |
| Data Analyst | 界定证据究竟支持什么 |
| Strategy Analyst | 比较行动反事实与取舍 |
| Anti-Fraud Specialist | 检查对抗适应与规避 |
| Model Engineer | 界定模型不确定性与失效 |
| Risk Platform Engineer | 保证工程实现不扭曲判断合同 |
| Release Engineer | 准备或执行已经明确授权的可回滚动作 |
| Release Verifier | 独立验证动作声明 |

不是每个任务都经过全部角色。一个有界任务使用 Direct Run；只有真实并行、
依赖、等待、重试或受治理动作才生成 TaskGraph。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python scripts/verify_public_boundary.py
pytest
```

```python
from pathlib import Path

from planner.domain_pack import load_domain_pack
from planner.execution_planner import plan_runtime

pack = load_domain_pack(
    pack_root=Path("volunteer_pack"),
    manifest_path="manifest.yaml",
)
planned = plan_runtime(
    domain_pack=pack,
    question="Explore a counterfactual and competing hypothesis.",
    run_id="example-run",
)

print(planned.orchestration_mode)
print(planned.decision.active_roles)
```

这个问题会激活 `Strategy Analyst`，并保留 `Lead` 作为最终责任收口。

## 项目结构

| 路径 | 责任 |
|---|---|
| `planner/` | Task、Working Set、Direct Run、TaskGraph、角色激活、执行与安全边界 |
| `risk_methods/` | 与角色解耦的公开方法合同 |
| `volunteer_pack/roles/` | 八个角色的人类可读说明 |
| `volunteer_pack/skills/` | 通用团队与角色 Skill |
| `volunteer_pack/*.yaml` | 可运行的角色、路由、方法、Connector 与 executor 组合 |
| `tests/` | Core、Pack、角色资产、隐私和判断收口验证 |

进一步阅读：[架构](docs/architecture.md)、[角色与技能](docs/roles-and-skills.md)、
[快速开始](docs/quickstart.md) 和 [公开边界](docs/public-boundary.md)。

## 安全

Arion Volunteer 默认只做本地执行，不授予任何外部写权限。Release 角色只表达
责任边界；真实项目仍须自行提供明确授权、适配器和独立控制。

## License

Apache License 2.0。
