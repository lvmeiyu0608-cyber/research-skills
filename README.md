# Research Skills for Management & IS

面向管理学 / 信息系统研究的 Agent Skills。每个 skill 是一个文件夹，核心是 `SKILL.md`，可选附带脚本和参考资料。

## Skills

| Skill | 用途 |
|---|---|
| [research-data-analysis](skills/research-data-analysis/) | 数据分析与前提核查：先确认数据、再查前提、后建模型；区分统计结果、解释与待检验设想；列出需研究者核验的事项。也可用于复现已发表论文并检查其分析。 |

## 目录结构

```
skills/
└── research-data-analysis/
    ├── SKILL.md                  # 流程、规则、输出格式（必需）
    ├── scripts/
    │   └── data_profile.py       # 只读的数据概况与前提初检
    └── references/
        ├── method-decision-tree.md
        ├── assumption-checklist.md
        └── test-cases.md
```

## 使用方法

- **Claude**：把 `skills/research-data-analysis` 文件夹压缩成 zip，在 Customize → Skills 中上传；提问时可点名"用 research-data-analysis skill"。
- **其他支持 Agent Skills 的平台**：按平台说明导入整个文件夹。
- **不支持 skill 的平台**：可把 `SKILL.md` 和需要的参考文件内容粘贴进对话手动使用（这不等于安装）。

数据检查脚本单独运行：

```bash
pip install pandas numpy scipy statsmodels
python skills/research-data-analysis/scripts/data_profile.py --data your_data.csv --id firm_id --time year
```

## 使用前须知

- 本 skill 是个人研究用的工作流程，**未经系统验证**；输出需要研究者自行核查。
- 方法清单中的阈值标为"暂定做法"，请以你的方法教材、导师要求和期刊惯例为准。
- 安装他人 skill 前，请先通读全部内容（包括脚本）。
- 不要用它处理未经授权的保密数据。

## License

MIT
