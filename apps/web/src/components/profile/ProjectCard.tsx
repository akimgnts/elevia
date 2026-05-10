import React from "react";

type ProjectCardProps = {
  project: {
    title?: string;
    impact?: string;
    technologies?: string[];
    url?: string;
    source?: "profile" | "suggestion";
  };
};

export const ProjectCard: React.FC<ProjectCardProps> = ({ project }) => {
  if (!project.title) {
    return null;
  }

  return (
    <article className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <h4 className="text-sm font-semibold text-slate-950">
            {project.title}
          </h4>
        </div>
        {project.source === "suggestion" && (
          <span className="whitespace-nowrap rounded-full bg-cyan-100 px-2 py-1 text-[10px] font-semibold uppercase text-cyan-700">
            Suggestion
          </span>
        )}
      </div>

      {project.impact && (
        <p className="mt-2 text-sm leading-6 text-slate-600">
          {project.impact}
        </p>
      )}

      {project.technologies && project.technologies.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {project.technologies.map((tech, idx) => (
            <span
              key={idx}
              className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-700 border border-slate-200"
            >
              {tech}
            </span>
          ))}
        </div>
      )}
    </article>
  );
};

export default ProjectCard;
