import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {BaseProps, inOut, resolveTheme, unit} from '../theme';

export type TitleCardProps = BaseProps & {
  kicker?: string;
  title: string;
  subtitle?: string;
  align?: 'center' | 'left';
  /** none = transparan, dim = gelapkan footage di bawahnya, paper = tekstur kertas (bgImage) */
  background?: 'none' | 'dim' | 'paper';
  bgImage?: string;
};

export const TitleCard: React.FC<TitleCardProps> = (p) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const t = resolveTheme(p.theme);
  const u = unit(width, height);
  const a = inOut(frame, fps, durationInFrames);
  const b = inOut(frame, fps, durationInFrames, 6);
  const c = inOut(frame, fps, durationInFrames, 12);
  const left = p.align === 'left';
  const bgOpacity = interpolate(a.v, [0, 1], [0, 1]);
  return (
    <AbsoluteFill style={{fontFamily: t.font, color: t.text}}>
      {p.background === 'dim' && <AbsoluteFill style={{background: 'rgba(0,0,0,0.45)', opacity: bgOpacity}} />}
      {p.background === 'paper' && p.bgImage && (
        <AbsoluteFill style={{opacity: bgOpacity}}>
          <Img src={staticFile(p.bgImage)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        </AbsoluteFill>
      )}
      <AbsoluteFill
        style={{
          justifyContent: 'center',
          alignItems: left ? 'flex-start' : 'center',
          padding: `0 ${8 * u}px`,
          textAlign: left ? 'left' : 'center',
        }}
      >
        {p.kicker && (
          <div
            style={{
              fontSize: 3.2 * u,
              letterSpacing: 0.5 * u,
              textTransform: 'uppercase',
              fontWeight: 700,
              color: t.accent,
              opacity: a.v,
              transform: `translateY(${(1 - a.enter) * 3 * u}px)`,
            }}
          >
            {p.kicker}
          </div>
        )}
        <div
          style={{
            fontSize: 9 * u,
            fontWeight: 800,
            lineHeight: 1.05,
            marginTop: 1.5 * u,
            opacity: b.v,
            transform: `translateY(${(1 - b.enter) * 4 * u}px)`,
            textShadow: p.background === 'none' || !p.background ? '0 0.4vmin 2vmin rgba(0,0,0,0.55)' : undefined,
          }}
        >
          {p.title}
        </div>
        {p.subtitle && (
          <div
            style={{
              fontSize: 3.8 * u,
              marginTop: 2.2 * u,
              color: t.muted,
              opacity: c.v,
              transform: `translateY(${(1 - c.enter) * 3 * u}px)`,
            }}
          >
            {p.subtitle}
          </div>
        )}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
