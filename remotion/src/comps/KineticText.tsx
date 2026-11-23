import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {BaseProps, resolveTheme, unit} from '../theme';

export type KineticWord = {
  text: string;
  at: number; // detik, biasanya diambil dari beats.json
  until?: number; // default: sampai kata berikutnya
  accent?: boolean;
};

export type KineticTextProps = BaseProps & {
  words: KineticWord[];
  size?: number; // dalam unit (default 12)
  position?: 'center' | 'bottom';
};

/** Teks besar yang menghentak mengikuti beat musik — untuk headliner/sizzle reel. */
export const KineticText: React.FC<KineticTextProps> = (p) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = resolveTheme(p.theme);
  const u = unit(width, height);
  const now = frame / fps;
  const words = [...p.words].sort((a, b) => a.at - b.at);
  const idx = words.findIndex((w, i) => now >= w.at && now < (w.until ?? words[i + 1]?.at ?? p.duration));
  if (idx < 0) return null;
  const w = words[idx];
  const local = frame - Math.round(w.at * fps);
  const end = (w.until ?? words[idx + 1]?.at ?? p.duration) * fps - frame;
  const pop = spring({frame: local, fps, config: {damping: 12, stiffness: 220, mass: 0.6}});
  const scale = interpolate(pop, [0, 1], [1.35, 1]);
  const opacity = Math.min(interpolate(local, [0, 2], [0, 1], {extrapolateRight: 'clamp'}), interpolate(end, [0, 3], [0, 1], {extrapolateRight: 'clamp'}));
  return (
    <AbsoluteFill
      style={{
        justifyContent: p.position === 'bottom' ? 'flex-end' : 'center',
        alignItems: 'center',
        paddingBottom: p.position === 'bottom' ? 12 * u : 0,
        fontFamily: t.font,
      }}
    >
      <div
        style={{
          fontSize: (p.size ?? 12) * u,
          fontWeight: 900,
          textTransform: 'uppercase',
          letterSpacing: -0.2 * u,
          color: w.accent ? t.accent : t.text,
          transform: `scale(${scale})`,
          opacity,
          textAlign: 'center',
          maxWidth: '90%',
          lineHeight: 1,
          textShadow: '0 0.5vmin 3vmin rgba(0,0,0,0.5)',
        }}
      >
        {w.text}
      </div>
    </AbsoluteFill>
  );
};
