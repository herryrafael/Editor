import React from 'react';
import {Composition} from 'remotion';
import {metadata} from './theme';
import {TitleCard} from './comps/TitleCard';
import {LowerThird} from './comps/LowerThird';
import {LocationTag} from './comps/LocationTag';
import {ChapterCard} from './comps/ChapterCard';
import {KineticText} from './comps/KineticText';
import {Collage} from './comps/Collage';
import {EndCard} from './comps/EndCard';

const base = {duration: 5, fps: 25, width: 1920, height: 1080};

// Semua komposisi = overlay transparan. Durasi/fps/ukuran diambil dari props (diisi `vedit gfx`).
export const Root: React.FC = () => (
  <>
    <Composition
      id="TitleCard"
      component={TitleCard}
      calculateMetadata={metadata}
      defaultProps={{...base, kicker: 'Dokumentasi', title: 'Judul Acara', subtitle: 'Jakarta · 12 Maret 2026', background: 'dim' as const}}
    />
    <Composition
      id="LowerThird"
      component={LowerThird}
      calculateMetadata={metadata}
      defaultProps={{...base, name: 'Nama Pembicara', role: 'CEO, Perusahaan'}}
    />
    <Composition
      id="LocationTag"
      component={LocationTag}
      calculateMetadata={metadata}
      defaultProps={{...base, place: 'Ubud, Bali', detail: 'Hari 2 · 14 Mar 2026'}}
    />
    <Composition
      id="ChapterCard"
      component={ChapterCard}
      calculateMetadata={metadata}
      defaultProps={{...base, number: 'BAGIAN 01', title: 'Pembukaan', mode: 'overlay' as const}}
    />
    <Composition
      id="KineticText"
      component={KineticText}
      calculateMetadata={metadata}
      defaultProps={{
        ...base,
        words: [
          {text: 'Satu', at: 0.2},
          {text: 'Visi', at: 0.8, accent: true},
          {text: 'Bersama', at: 1.4},
        ],
      }}
    />
    <Composition
      id="Collage"
      component={Collage}
      calculateMetadata={metadata}
      defaultProps={{...base, pieces: []}}
    />
    <Composition
      id="EndCard"
      component={EndCard}
      calculateMetadata={metadata}
      defaultProps={{...base, lines: ['Terima kasih'], footer: 'www.contoh.id'}}
    />
  </>
);
