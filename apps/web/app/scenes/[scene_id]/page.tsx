import { SharedSceneDetail } from "@/features/shared-scenes/SharedSceneDetail";

export default async function ScenePage({ params }: { params: Promise<{ scene_id: string }> }) {
  const { scene_id } = await params;
  return <SharedSceneDetail sceneId={scene_id} />;
}
