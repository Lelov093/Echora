# Echora Web

Echora 的用户界面，基于 Next.js 16、React 19、TypeScript 与 TanStack Query。

Web 端围绕普通用户的伙伴体验组织：创建与管理伙伴、沉浸对话、记忆修正、成长理解、Presence、工具、Discord 和可编辑设置。诊断、策略证据与原始运行记录只作为按需高级信息，不作为产品主界面。

## 本机运行

在仓库根目录完成 `.env` 和后端配置后：

```powershell
Set-Location apps\web
npm ci
npm run dev
```

访问 <http://localhost:3000>。默认 Agent API 地址为 `http://127.0.0.1:8010/api/v1`；需要覆盖时设置：

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010/api/v1
```

## 主要目录

```text
app/          Next.js App Router 页面与 canonical routes
components/   通用交互、对话与设置组件
features/     按产品领域组织的完整功能工作区
lib/api/      Agent API typed clients
lib/hooks/    查询与运行时 hooks
styles/       Echora 浅色叙事式视觉语言
scripts/      契约与回归检查
```

## 验证

```powershell
npm run lint
npx tsc --noEmit
npm run build
npm run check:product-contract
```

`check:product-contract` 检查公开产品入口和关键体验契约；仓库根目录的
`check-public-release.ps1` 与 `check-public-language.ps1` 分别检查公开文件边界和内部开发语言。
这些检查不替代真实后端测试或人工体验验收。

## 前端约束

- 所有伙伴身份、记忆、关系、成长、Presence 和渠道状态必须保持 Companion scope。
- 用户设置必须连接真实 API，不能以静态成功状态或模拟结果代替闭环。
- 不展示或持久化模型 reasoning content；“回复依据”只展示高层 workflow 与可审计证据。
- 普通页面使用中文产品语言；Trace ID、contract revision 和策略枚举只在必要的高级详情中出现。
- 视觉保持浅色、留白、低饱和星蓝／柔紫／薄荷与清晰焦点态。
