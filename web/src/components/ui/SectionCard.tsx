import type React from "react";
import { Card } from "./Card";

interface SectionCardProps {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}

export function SectionCard({ icon, title, children }: SectionCardProps) {
  return (
    <Card className="p-6 space-y-4">
      <div className="flex items-center gap-2 text-lg font-semibold text-fg">
        {icon}
        {title}
      </div>
      {children}
    </Card>
  );
}
