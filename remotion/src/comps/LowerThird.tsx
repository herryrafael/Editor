import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {BaseProps, inOut, resolveTheme, unit} from '../theme';

export type LowerThirdProps = BaseProps & {
  name: string;
  role?: string;
  side?: 'left' | 'right';
};

/** Nama + jabatan narasumber / pembicara. */
export const LowerThird: React.FC<LowerThirdProps> = (p) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const t = resolveTheme(p.theme);
  const u = unit(width, height);
  const bar = inOut(frame, fps, durationInFrames);
  const txt = inOut(frame, fps, durationInFrames, 5);
  const right = p.side === 'right';
  return (
    <AbsoluteFill style={{fontFamily: t.font}}>
      <div
        style={{
          position: 'absolute',
          bottom: 9 * u,
          [right ? 'right' : 'left']: 6 * u,
          display: 'flex',
          flexDirection: right ? 'row-reverse' : 'row',
          alignItems: 'stretch',
          opacity: bar.exit,
        }}
      >
        <div style={{width: 0.9 * u, background: t.accent, transform: `scaleY(${bar.enter})`}} />
        <div
          style={{
            background: t.panel,
            padding: `${1.6 * u}px ${2.6 * u}px`,
            clipPath: `inset(0 ${right ? 0 : (1 - bar.enter) * 100}% 0 ${right ? (1 - bar.enter) * 100 : 0}%)`,
            textAlign: right ? 'right' : 'left',
          }}
        >
          <div style={{color: t.text, fontSize: 4.2 * u, fontWeight: 800, opacity: txt.v}}>{p.name}</div>
          {p.role && (
            <div style={{color: t.muted, fontSize: 2.8 * u, marginTop: 0.5 * u, opacity: txt.v}}>{p.role}</div>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};
