import {Easing, interpolate, spring} from 'remotion';

export type Theme = {
  font?: string;
  accent?: string;
  text?: string;
  muted?: string;
  panel?: string;
};

export type BaseProps = {
  duration: number;
  fps: number;
  width: number;
  height: number;
  theme?: Theme;
};

export const resolveTheme = (t?: Theme) => ({
  font: t?.font ?? "Inter, 'Helvetica Neue', Arial, sans-serif",
  accent: t?.accent ?? '#E63946',
  text: t?.text ?? '#FFFFFF',
  muted: t?.muted ?? 'rgba(255,255,255,0.75)',
  panel: t?.panel ?? 'rgba(10,12,18,0.72)',
});

// Ukuran relatif terhadap sisi pendek supaya aman di 16:9 maupun 9:16.
export const unit = (width: number, height: number) => Math.min(width, height) / 100;

export const metadata = ({props}: {props: BaseProps}) => ({
  durationInFrames: Math.max(1, Math.round(props.duration * props.fps)),
  fps: props.fps,
  width: props.width,
  height: props.height,
});

/** Masuk dengan spring, keluar dengan fade di detik-detik terakhir. */
export const inOut = (frame: number, fps: number, total: number, delay = 0, outSec = 0.5) => {
  const enter = spring({frame: frame - delay, fps, config: {damping: 200}, durationInFrames: Math.round(fps * 0.6)});
  const exit = interpolate(frame, [total - outSec * fps, total], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.in(Easing.cubic),
  });
  return {enter, exit, v: Math.min(enter, exit)};
};

export const src = (s: string) => s;
