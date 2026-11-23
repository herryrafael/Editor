import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {BaseProps, inOut, resolveTheme, unit} from '../theme';

export type LocationTagProps = BaseProps & {
  place: string;
  detail?: string; // mis. "Hari 2 · 14 Mar 2026" atau koordinat
  corner?: 'top-left' | 'bottom-left' | 'top-right';
};

/** Penanda lokasi untuk video travel / acara multi-venue. */
export const LocationTag: React.FC<LocationTagProps> = (p) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const t = resolveTheme(p.theme);
  const u = unit(width, height);
  const a = inOut(frame, fps, durationInFrames);
  const corner = p.corner ?? 'top-left';
  const pos: React.CSSProperties = {
    position: 'absolute',
    [corner.startsWith('top') ? 'top' : 'bottom']: 7 * u,
    [corner.endsWith('left') ? 'left' : 'right']: 6 * u,
  };
  return (
    <AbsoluteFill style={{fontFamily: t.font}}>
      <div style={{...pos, display: 'flex', alignItems: 'center', gap: 1.6 * u, opacity: a.v}}>
        <svg width={5 * u} height={5 * u} viewBox="0 0 24 24" style={{transform: `translateY(${(1 - a.enter) * -2 * u}px)`}}>
          <path
            d="M12 2C8 2 5 5.1 5 9c0 5.2 7 13 7 13s7-7.8 7-13c0-3.9-3-7-7-7zm0 9.5a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5z"
            fill={t.accent}
          />
        </svg>
        <div style={{transform: `translateX(${(1 - a.enter) * 3 * u}px)`}}>
          <div style={{color: t.text, fontSize: 4 * u, fontWeight: 800, textShadow: '0 0.3vmin 1.5vmin rgba(0,0,0,0.6)'}}>
            {p.place}
          </div>
          {p.detail && (
            <div style={{color: t.muted, fontSize: 2.6 * u, textShadow: '0 0.3vmin 1.5vmin rgba(0,0,0,0.6)'}}>{p.detail}</div>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};
