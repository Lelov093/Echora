import Link from "next/link";

export default function ToolsPageBody() {
  return (
    <main className="detail-workspace">
      <header className="detail-hero">
        <div><p>设置 / 交互与能力</p><h1>工具治理已迁移</h1><span>工具选择与执行从 Conversation 发起；定义、权限和运行证据统一在设置中查看。</span></div>
      </header>
      <Link className="detail-action detail-action-primary" href="/settings/tools">打开工具治理</Link>
    </main>
  );
}
