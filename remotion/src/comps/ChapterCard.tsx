import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {BaseProps, inOut, resolveTheme, unit} from '../theme';

export type ChapterCardProps = BaseProps & {
  number?: string; // "01" / "Hari 1" / "Bab 2"
  title: string;
  /** solid = layar penuh menutupi footage, overlay = garis + teks di atas footage */
  mode?: 'solid' | 'overlay';
  bg?: string;
};

/** Pembatas bab — penting untuk video 15 menit – 2 jam supaya penonton tahu posisi. */
export const ChapterCard: React.FC<ChapterCardProps> = (p) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const t = resolveTheme(p.theme);
  const u = unit(width, height);
  const a = inOut(frame, fps, durationInFrames);
  const b = inOut(frame, fps, durationInFrames, 8);
  const line = interpolate(a.enter, [0, 1], [0, 18 * u]);
  return (
    <AbsoluteFill style={{fontFamily: t.font, color: t.text}}>
      {p.mode === 'solid' && <AbsoluteFill style={{background: p.bg ?? '#0d0f14', opacity: a.exit}} />}
      {p.mode !== 'solid' && <AbsoluteFill style={{background: 'rgba(0,0,0,0.35)', opacity: a.v}} />}
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', textAlign: 'center'}}>
        {p.number && (
          <div style={{fontSize: 3.4 * u, fontWeight: 700, color: t.accent, letterSpacing: 0.6 * u, opacity: a.v}}>
            {p.number}
          </div>
        )}
        <div style={{height: 0.5 * u, width: line, background: t.accent, margin: `${2 * u}px 0`, opacity: a.exit}} />
        <div
          style={{
            fontSize: 7.5 * u,
            fontWeight: 800,
            maxWidth: '80%',
            lineHeight: 1.1,
            opacity: b.v,
            transform: `translateY(${(1 - b.enter) * 3 * u}px)`,
          }}
        >
          {p.title}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
