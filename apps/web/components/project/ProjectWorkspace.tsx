"use client";

import { useState } from "react";
import { CheckCircle2, Link2, Plus, RefreshCw } from "lucide-react";
import { completeProjectTask, createProjectTask, createProjectTaskEvidenceLink } from "@/lib/api/projects";
import { ListControls } from "@/components/list/ListControls";
import { useProjectMilestones, useProjectTasks } from "@/lib/hooks/useProjectData";
import { useClientListControls } from "@/lib/hooks/useClientListControls";
import type { ProjectMilestone } from "@/lib/api/projects";
import type { ProjectTask } from "@/lib/types";

export function ProjectWorkspace() {
  const milestones = useProjectMilestones(30);
  const tasks = useProjectTasks(undefined, 50);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const taskList = useClientListControls<ProjectTask>({
    items: tasks.items,
    searchText: (item) => `${item.title ?? ""} ${item.status ?? ""} ${item.evidence_summary ?? ""}`,
    status: (item) => item.status,
    initialPageSize: 10,
  });
  const milestoneList = useClientListControls<ProjectMilestone>({
    items: milestones.items,
    searchText: (item) => `${item.title ?? ""} ${item.status ?? ""}`,
    status: (item) => item.status,
    initialPageSize: 10,
  });

  async function reloadAll() {
    await Promise.all([milestones.reload(), tasks.reload()]);
  }

  async function act(label: string, action: () => Promise<unknown>) {
    setBusy(label);
    setError(null);
    try {
      await action();
      await reloadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  function addTask() {
    return act("add-task", () => createProjectTask({
      title: "Project follow-up",
      status: "todo",
      priority: 2,
      evidence_summary: "Created from Project Workspace",
    }));
  }

  return (
    <div className="agent-lab-page">
      <section className="agent-lab-hero dynamic-glass">
        <div>
          <div className="agent-lab-eyebrow">Project Workspace</div>
          <h1>Tasks with evidence</h1>
          <p>{taskList.total} tasks / {milestoneList.total} milestones</p>
        </div>
        <div className="agent-lab-actions">
          <button type="button" className="tool-icon-btn" aria-label="Refresh projects" onClick={reloadAll}>
            <RefreshCw size={17} />
          </button>
          <button type="button" className="glass-btn-primary agent-lab-action" onClick={addTask} disabled={busy !== null}>
            <Plus size={16} /> Add task
          </button>
        </div>
      </section>

      {error && <div className="tool-error glass-soft">{error}</div>}

      <div className="agent-lab-grid">
        <section className="agent-lab-panel glass-soft">
          <div className="agent-lab-panel-head"><h2>Tasks</h2><span>{tasks.loading ? "loading" : taskList.total}</span></div>
          <ListControls
            label="Project task controls"
            query={taskList.query}
            onQueryChange={taskList.setQuery}
            status={taskList.status}
            onStatusChange={taskList.setStatus}
            statuses={taskList.statuses}
            page={taskList.page}
            pageSize={taskList.pageSize}
            total={taskList.total}
            onPageChange={taskList.setPage}
            onPageSizeChange={taskList.setPageSize}
          />
          <div className="agent-lab-list">
            {taskList.pageItems.map((task) => (
              <article key={task.id} className="agent-lab-row">
                <div>
                  <strong>{task.title}</strong>
                  <span>{task.status} / priority {task.priority ?? 0}</span>
                  {task.evidence_summary && <p>{task.evidence_summary}</p>}
                </div>
                <div className="agent-lab-row-actions">
                  <button type="button" aria-label="Complete task" onClick={() => act(task.id, () => completeProjectTask(task.id))}>
                    <CheckCircle2 size={16} />
                  </button>
                  <button
                    type="button"
                    aria-label="Link evidence"
                    onClick={() => act(`${task.id}-evidence`, () => createProjectTaskEvidenceLink(task.id, {
                      evidence_type: "trace",
                      relevance_score: 0.5,
                    }))}
                  >
                    <Link2 size={16} />
                  </button>
                </div>
              </article>
            ))}
            {!tasks.loading && taskList.pageItems.length === 0 && <div className="tool-empty">No project tasks yet.</div>}
          </div>
        </section>

        <section className="agent-lab-panel glass-soft">
          <div className="agent-lab-panel-head"><h2>Milestones</h2><span>{milestones.loading ? "loading" : milestoneList.total}</span></div>
          <ListControls
            label="Project milestone controls"
            query={milestoneList.query}
            onQueryChange={milestoneList.setQuery}
            status={milestoneList.status}
            onStatusChange={milestoneList.setStatus}
            statuses={milestoneList.statuses}
            page={milestoneList.page}
            pageSize={milestoneList.pageSize}
            total={milestoneList.total}
            onPageChange={milestoneList.setPage}
            onPageSizeChange={milestoneList.setPageSize}
          />
          <div className="agent-lab-list">
            {milestoneList.pageItems.map((milestone) => (
              <article key={milestone.id} className="agent-lab-row">
                <div>
                  <strong>{milestone.title}</strong>
                  <span>{milestone.status} / priority {milestone.priority ?? 0}</span>
                </div>
              </article>
            ))}
            {!milestones.loading && milestoneList.pageItems.length === 0 && <div className="tool-empty">No milestones yet.</div>}
          </div>
        </section>
      </div>
    </div>
  );
}
