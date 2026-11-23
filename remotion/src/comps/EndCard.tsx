import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {BaseProps, inOut, resolveTheme, unit} from '../theme';

export type EndCardProps = BaseProps & {
  logo?: string;
  lines?: string[]; // mis. ["Terima kasih", "Jakarta, 12 Maret 2026"]
  footer?: string; // url / sosmed
  bg?: string; // warna latar; kosong = transparan
};

export const EndCard: React.FC<EndCardProps> = (p) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const t = resolveTheme(p.theme);
  const u = unit(width, height);
  const a = inOut(frame, fps, durationInFrames, 0, 0.8);
  return (
    <AbsoluteFill style={{fontFamily: t.font, color: t.text}}>
      {p.bg && <AbsoluteFill style={{background: p.bg, opacity: a.exit}} />}
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', textAlign: 'center', gap: 2.5 * u}}>
        {p.logo && (
          <Img
            src={staticFile(p.logo)}
            style={{maxWidth: '40%', maxHeight: 22 * u, opacity: a.v, transform: `scale(${0.9 + 0.1 * a.enter})`}}
          />
        )}
        {(p.lines ?? []).map((l, i) => {
          const b = inOut(frame, fps, durationInFrames, 6 + i * 5, 0.8);
          return (
            <div key={i} style={{fontSize: (i === 0 ? 5.5 : 3.2) * u, fontWeight: i === 0 ? 800 : 500, opacity: b.v, color: i === 0 ? t.text : t.muted}}>
              {l}
            </div>
          );
        })}
        {p.footer && <div style={{fontSize: 2.6 * u, color: t.accent, opacity: a.v, marginTop: 2 * u}}>{p.footer}</div>}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
