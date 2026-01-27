import * as React from "react";
import { cn } from "../../lib/cn";
import { layout } from "../../styles/uiTokens";

export function PageContainer({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(layout.container, className)}
      {...props}
    />
  );
}
