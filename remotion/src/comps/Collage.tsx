import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {BaseProps, resolveTheme, unit} from '../theme';

export type CollagePiece = {
  src: string; // PNG transparan (hasil `vedit key` dari aset Gemini)
  x: number; // 0–100 (% lebar)
  y: number; // 0–100 (% tinggi)
  w: number; // lebar dalam % lebar frame
  rotate?: number;
  at?: number; // detik muncul
  caption?: string;
};

export type CollageProps = BaseProps & {
  pieces: CollagePiece[];
  bgImage?: string; // tekstur kertas penuh (opsional)
  drift?: boolean; // gerak lambat supaya tidak kaku
};

/** Gaya kolase/cutout kertas: potongan aset muncul satu per satu dengan bayangan. */
export const Collage: React.FC<CollageProps> = (p) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const t = resolveTheme(p.theme);
  const u = unit(width, height);
  const exit = interpolate(frame, [durationInFrames - fps * 0.4, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill style={{opacity: exit, fontFamily: t.font}}>
      {p.bgImage && <Img src={staticFile(p.bgImage)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />}
      {p.pieces.map((pc, i) => {
        const start = Math.round((pc.at ?? i * 0.25) * fps);
        const s = spring({frame: frame - start, fps, config: {damping: 14, stiffness: 160}});
        const drift = p.drift === false ? 0 : Math.sin((frame + i * 40) / (fps * 2)) * 0.6;
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: `${pc.x}%`,
              top: `${pc.y}%`,
              width: `${pc.w}%`,
              transform: `translate(-50%, -50%) rotate(${(pc.rotate ?? 0) + drift}deg) scale(${interpolate(s, [0, 1], [0.6, 1])})`,
              opacity: Math.min(1, s * 1.5),
              filter: 'drop-shadow(0 1.2vmin 1.6vmin rgba(0,0,0,0.35))',
            }}
          >
            <Img src={staticFile(pc.src)} style={{width: '100%'}} />
            {pc.caption && (
              <div
                style={{
                  marginTop: 0.8 * u,
                  background: '#fffdf5',
                  color: '#1b1b1b',
                  fontSize: 2.4 * u,
                  fontWeight: 700,
                  padding: `${0.5 * u}px ${1.2 * u}px`,
                  display: 'inline-block',
                }}
              >
                {pc.caption}
              </div>
            )}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
