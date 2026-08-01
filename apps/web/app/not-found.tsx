import Link from "next/link";
import { DataState } from "@/components/patterns/DataState";

export default function NotFound() {
  return <DataState kind="empty" title="没有找到这个空间" description="它可能已移动，或当前伙伴没有访问权限。" action={<Link className="echora-state-action" href="/">返回伙伴星图</Link>} />;
}
