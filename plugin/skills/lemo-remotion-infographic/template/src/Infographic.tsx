// Props-driven infographic: every word, number, colour and timing comes from props.json.
// Edit props (or the plan they came from), not this file, when making a film.
// Layout is derived from the frame: 1920x1080 or 1080x1920 (portrait keeps text inside y 220..1600,
// the same safe band the library's native 9:16 styles use).
import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  Sequence,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { InfographicProps, Line, Scene } from "./types";

type Ctx = { p: InfographicProps; portrait: boolean; W: number; H: number };

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const fmt = (v: number, lang: string) =>
  v.toLocaleString(lang === "en" ? "en-US" : "zh-CN", { maximumFractionDigits: 1 });

// Fade in over 8 frames, out over the last 6: scenes cut cleanly on the props' frame grid.
const useEnvelope = (dur: number) => {
  const f = useCurrentFrame();
  return interpolate(f, [0, 8, dur - 6, dur], [0, 1, 1, 0], clamp);
};

const Lines: React.FC<{ ctx: Ctx; lines: Line[]; size: number; weight?: number; align?: "left" | "center" }> = ({
  ctx,
  lines,
  size,
  weight = 800,
  align = "left",
}) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <div style={{ textAlign: align, fontFamily: ctx.p.fonts.display, fontWeight: weight }}>
      {lines.map((line, i) => {
        const s = spring({ frame: f - i * 4, fps, config: { damping: 200 } });
        return (
          <div
            key={i}
            style={{
              fontSize: size,
              lineHeight: 1.12,
              transform: `translateY(${(1 - s) * size * 0.4}px)`,
              opacity: s,
              wordBreak: "break-word",
            }}
          >
            {line.map((seg, j) => (
              <span key={j} style={{ color: seg.accent ? ctx.p.palette.accent : ctx.p.palette.ink }}>
                {seg.text}
              </span>
            ))}
          </div>
        );
      })}
    </div>
  );
};

const Frame: React.FC<{ ctx: Ctx; children: React.ReactNode; justify?: "center" | "flex-end" }> = ({
  ctx,
  children,
  justify = "center",
}) => (
  <AbsoluteFill
    style={{
      padding: ctx.portrait ? "220px 72px 320px" : "120px 140px",
      justifyContent: justify,
      fontFamily: ctx.p.fonts.text,
      color: ctx.p.palette.ink,
    }}
  >
    {children}
  </AbsoluteFill>
);

const Title: React.FC<{ ctx: Ctx; s: Scene }> = ({ ctx, s }) => {
  const f = useCurrentFrame();
  const bar = interpolate(f, [6, 24], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  return (
    <Frame ctx={ctx}>
      <Lines ctx={ctx} lines={s.lines} size={ctx.portrait ? 150 : 170} />
      <div style={{ height: 14, width: `${bar * 40}%`, background: ctx.p.palette.accent, marginTop: 40 }} />
    </Frame>
  );
};

const Chapter: React.FC<{ ctx: Ctx; s: Scene; index: number }> = ({ ctx, s, index }) => (
  <Frame ctx={ctx}>
    <div
      style={{
        fontFamily: ctx.p.fonts.text,
        fontWeight: 700,
        fontSize: 64,
        color: ctx.p.palette.accent,
        marginBottom: 24,
        fontVariantNumeric: "tabular-nums",
      }}
    >
      {String(index).padStart(2, "0")}
    </div>
    <Lines ctx={ctx} lines={s.lines} size={ctx.portrait ? 120 : 130} />
  </Frame>
);

// Keyword caption bar: a lower-third panel that also reads over a style render (overlay mode).
const Caption: React.FC<{ ctx: Ctx; s: Scene }> = ({ ctx, s }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const x = spring({ frame: f, fps, config: { damping: 200 } });
  const segs = s.lines.flat();
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", padding: ctx.portrait ? "0 72px 360px" : "0 140px 120px" }}>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 20,
          alignItems: "center",
          padding: "28px 36px",
          background: ctx.p.palette.bg,
          borderLeft: `14px solid ${ctx.p.palette.accent}`,
          transform: `translateX(${(1 - x) * -60}px)`,
          opacity: x,
          fontFamily: ctx.p.fonts.display,
          fontWeight: 800,
          fontSize: ctx.portrait ? 84 : 92,
          lineHeight: 1.15,
          alignSelf: "flex-start",
          maxWidth: "100%",
        }}
      >
        {segs.map((seg, j) => (
          <span
            key={j}
            style={
              seg.accent
                ? { background: ctx.p.palette.accent, color: ctx.p.palette.bg, padding: "0 16px" }
                : { color: ctx.p.palette.ink }
            }
          >
            {seg.text}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const BigNumber: React.FC<{ ctx: Ctx; s: Scene }> = ({ ctx, s }) => {
  const f = useCurrentFrame();
  const t = interpolate(f, [0, Math.min(36, s.durationInFrames - 8)], [0, 1], {
    ...clamp,
    easing: Easing.out(Easing.cubic),
  });
  const v = s.number ?? 0;
  const shown = Math.round(v * t * 10) / 10;
  return (
    <Frame ctx={ctx}>
      <div
        style={{
          fontFamily: ctx.p.fonts.text,
          fontWeight: 800,
          fontSize: ctx.portrait ? 260 : 300,
          lineHeight: 1,
          color: ctx.p.palette.accent,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {fmt(shown, ctx.p.language)}
        {s.unit ? <span style={{ fontSize: "0.35em", marginLeft: 16 }}>{s.unit}</span> : null}
      </div>
      <div style={{ marginTop: 40 }}>
        <Lines ctx={ctx} lines={s.lines} size={ctx.portrait ? 88 : 96} />
      </div>
    </Frame>
  );
};

const Compare: React.FC<{ ctx: Ctx; s: Scene }> = ({ ctx, s }) => {
  const f = useCurrentFrame();
  const items = s.items ?? [];
  const max = Math.max(1e-9, ...items.map((i) => i.value));
  return (
    <Frame ctx={ctx}>
      {s.lines.length ? (
        <div style={{ marginBottom: 56 }}>
          <Lines ctx={ctx} lines={s.lines} size={ctx.portrait ? 96 : 88} />
        </div>
      ) : null}
      {items.map((it, i) => {
        const g = interpolate(f, [4 + i * 6, 30 + i * 6], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
        return (
          <div key={i} style={{ marginBottom: ctx.portrait ? 72 : 48 }}>
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 24,
                fontFamily: ctx.p.fonts.display,
                fontWeight: 800,
                fontSize: ctx.portrait ? 80 : 72,
              }}
            >
              <span>{it.label}</span>
              {it.tag ? <span style={{ color: ctx.p.palette.accent }}>{it.tag}</span> : null}
              <span style={{ marginLeft: "auto", fontFamily: ctx.p.fonts.text, fontVariantNumeric: "tabular-nums" }}>
                {fmt(it.value * g, ctx.p.language)}
                {s.unit ? ` ${s.unit}` : ""}
              </span>
            </div>
            <div style={{ height: 36, background: ctx.p.palette.muted, marginTop: 16 }}>
              <div
                style={{
                  height: "100%",
                  width: `${Math.max(0.6, (it.value / max) * 100) * g}%`,
                  background: i === items.length - 1 ? ctx.p.palette.accent : ctx.p.palette.ink,
                }}
              />
            </div>
          </div>
        );
      })}
    </Frame>
  );
};

const Chart: React.FC<{ ctx: Ctx; s: Scene }> = ({ ctx, s }) => {
  const f = useCurrentFrame();
  const series = s.series ?? [];
  const max = Math.max(1e-9, ...series);
  const chartH = ctx.portrait ? 760 : 520;
  return (
    <Frame ctx={ctx}>
      <Lines ctx={ctx} lines={s.lines} size={ctx.portrait ? 96 : 88} />
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          gap: ctx.portrait ? 24 : 40,
          height: chartH,
          marginTop: 48,
          borderBottom: `6px solid ${ctx.p.palette.ink}`,
        }}
      >
        {series.map((v, i) => {
          const g = interpolate(f, [6 + i * 4, 30 + i * 4], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
          const last = i === series.length - 1;
          return (
            <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "flex-end", height: "100%" }}>
              <div
                style={{
                  textAlign: "center",
                  fontWeight: 700,
                  fontSize: ctx.portrait ? 48 : 44,
                  opacity: g,
                  marginBottom: 12,
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {fmt(v, ctx.p.language)}
              </div>
              <div
                style={{
                  height: `${Math.max(0.5, (v / max) * 100) * g * 0.86}%`,
                  background: last ? ctx.p.palette.accent : ctx.p.palette.ink,
                }}
              />
            </div>
          );
        })}
      </div>
    </Frame>
  );
};

const End: React.FC<{ ctx: Ctx; s: Scene }> = ({ ctx, s }) => {
  const c = ctx.p.credits;
  const credit = c ? [c.author, c.year, c.license].filter(Boolean).join(" · ") : "";
  return (
    <Frame ctx={ctx}>
      <Lines ctx={ctx} lines={s.lines} size={ctx.portrait ? 140 : 150} align="center" />
      {credit ? (
        <div style={{ textAlign: "center", marginTop: 48, fontSize: 40, color: ctx.p.palette.muted }}>{credit}</div>
      ) : null}
    </Frame>
  );
};

const SceneView: React.FC<{ ctx: Ctx; s: Scene; chapter: number }> = ({ ctx, s, chapter }) => {
  const env = useEnvelope(s.durationInFrames);
  const body = (() => {
    switch (s.kind) {
      case "title":
        return <Title ctx={ctx} s={s} />;
      case "chapter":
        return <Chapter ctx={ctx} s={s} index={chapter} />;
      case "caption":
        return <Caption ctx={ctx} s={s} />;
      case "bigNumber":
        return <BigNumber ctx={ctx} s={s} />;
      case "compare":
        return <Compare ctx={ctx} s={s} />;
      case "chart":
        return <Chart ctx={ctx} s={s} />;
      case "end":
        return <End ctx={ctx} s={s} />;
    }
  })();
  return <AbsoluteFill style={{ opacity: env }}>{body}</AbsoluteFill>;
};

export const Infographic: React.FC<InfographicProps> = (p) => {
  const { width, height } = useVideoConfig();
  const ctx: Ctx = { p, portrait: height > width, W: width, H: height };
  let chapter = 0;
  return (
    <AbsoluteFill style={{ background: p.transparent ? "transparent" : p.palette.bg }}>
      {p.scenes.map((s) => {
        if (s.kind === "chapter") chapter += 1;
        return (
          <Sequence key={s.id} from={s.from} durationInFrames={s.durationInFrames} name={`${s.id} ${s.kind}`}>
            <SceneView ctx={ctx} s={s} chapter={chapter} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
