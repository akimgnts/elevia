import * as React from "react";

type DivProps = React.HTMLAttributes<HTMLDivElement>;

export function Card({ children, ...props }: DivProps) {
  return <div {...props}>{children}</div>;
}

