# .agent

存放项目级 Agent Skills 以及配合 Claude Code 使用的开发辅助配置。

## 与 `.claude/skills` 的关系

Claude Code 只会从 `.claude/skills/<name>/SKILL.md` 发现项目技能，**没有配置项可以指定其他技能目录**。因此本项目采用：

- 技能源文件放在 `.agent/skills/`，纳入 git 管理
- `.claude/skills` 是指向 `.agent/skills` 的目录联接（Windows junction / POSIX symlink），不纳入 git
- 新环境克隆后执行一次：

  ```bash
  uv run python scripts/setup_agent_skills.py
  # 或
  python scripts/setup_agent_skills.py
  ```

> Windows 下脚本使用 `mklink /J` 创建目录联接，不需要管理员权限。
> 新增或修改技能后，需要重启 Claude Code 会话才会重新加载。

## 目录结构

```
.agent/
├── README.md              # 本文件
├── templates/
│   └── SKILL.md           # 技能模板
└── skills/                # 技能源文件目录（通过联接暴露给 Claude Code）
    └── <skill-name>/
        ├── SKILL.md       # 必需，文件名固定
        └── references/    # 可选：参考资料、脚本等
```

## 新增技能

1. 复制模板：

   ```bash
   mkdir -p .agent/skills/<skill-name>
   cp .agent/templates/SKILL.md .agent/skills/<skill-name>/SKILL.md
   ```

2. 填写 frontmatter：
   - `name`：技能标识，使用 kebab-case
   - `description`：一句话说明技能做什么、模型在什么场景下应该使用它（这是自动触发的关键）
3. 在正文中写清使用步骤；内容较多时拆到同目录的 `references/` 下并在 `SKILL.md` 中引用
4. 重启会话后验证：用 `/skills` 查看，或直接描述任务让模型自动触发

## 注意事项

- 技能目录只扫描一层：`skills/<name>/SKILL.md`，不要把技能再分组嵌套
- `SKILL.md` 建议控制在 500 行以内，细节放到引用文件里
- 如果 Windows 下目录联接出现识别异常，可删除 `.claude/skills` 后重新执行脚本，或临时把技能直接放到 `.claude/skills/` 下
- 官方文档：<https://code.claude.com/docs/en/skills>
