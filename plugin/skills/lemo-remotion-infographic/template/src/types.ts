// Props contract. Mirrors props.schema.json (the schema is the source of truth;
// scripts/plan_to_props.py writes props that validate against it).

export type Segment = { text: string; accent: boolean };
export type Line = Segment[];

export type SceneKind = "title" | "chapter" | "caption" | "bigNumber" | "compare" | "chart" | "end";

export type Scene = {
  id: string;
  kind: SceneKind;
  role: string;
  from: number;
  durationInFrames: number;
  lines: Line[];
  voText?: string;
  number?: number;
  unit?: string;
  items?: { label: string; tag?: string; value: number }[];
  series?: number[];
};

export type InfographicProps = {
  schemaVersion: 1;
  fps: 24;
  aspect: "16:9" | "9:16";
  width: number;
  height: number;
  durationInFrames: number;
  language: "zh" | "en" | "zh-en";
  topic: string;
  transparent: boolean;
  palette: { bg: string; ink: string; accent: string; muted: string };
  fonts: { text: string; display: string };
  scenes: Scene[];
  credits?: { title?: string; author?: string; year?: string; license?: string };
};
