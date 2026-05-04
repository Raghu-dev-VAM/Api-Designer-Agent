import React from 'react';

interface IconProps {
  name: string;
  size?: number;
}

export default function Icon({ name, size = 18 }: IconProps) {
  const props = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  const filled = { width: size, height: size, viewBox: '0 0 24 24', fill: 'currentColor' };

  const icons: Record<string, React.ReactElement> = {
    logo: <svg {...props}><rect x="9" y="3" width="6" height="4" rx="1" /><rect x="3" y="16" width="6" height="4" rx="1" /><rect x="15" y="16" width="6" height="4" rx="1" /><path d="M12 7v6M6 16v-3h12v3" /></svg>,
    spark: <svg {...filled}><path d="m12 2 1.7 5.2L19 9l-5.3 1.8L12 16l-1.7-5.2L5 9l5.3-1.8L12 2ZM5 15l.8 2.2L8 18l-2.2.8L5 21l-.8-2.2L2 18l2.2-.8L5 15Zm14-1 1 3 3 1-3 1-1 3-1-3-3-1 3-1 1-3Z" /></svg>,
    plug: <svg {...props}><path d="M9 7V2M15 7V2M7 7h10v4a5 5 0 0 1-10 0V7ZM12 16v6" /></svg>,
    globe: <svg {...props}><circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20" /></svg>,
    diamond: <svg {...filled}><path d="m12 2 10 10-10 10L2 12 12 2Zm0 6-4 4 4 4 4-4-4-4Z" /></svg>,
    waves: <svg {...filled}><path d="M4 4h9l7 5-5 4 5 4-4 3-7-5H4l5-4-5-4Z" /></svg>,
    folder: <svg {...filled}><path d="M3 6.5A2.5 2.5 0 0 1 5.5 4h4L12 6h6.5A2.5 2.5 0 0 1 21 8.5v8A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5v-10Z" /></svg>,
    sheet: <svg {...filled}><path d="M5 3h10l4 4v14H5V3Zm9 1v4h4M8 9h8M8 13h8M8 17h8" /></svg>,
    azure: <svg {...filled}><path d="M13.4 3 4 6.7v8.6L13.4 21 20 17.8V6.1L13.4 3Zm0 2.7v12.6L7 14.6V8.3l6.4-2.6Z" /></svg>,
    check: <svg {...props}><path d="m20 6-11 11-5-5" /></svg>,
    search: <svg {...props}><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></svg>,
    filter: <svg {...props}><path d="M22 3H2l8 9.5V19l4 2v-8.5L22 3Z" /></svg>,
    arrow: <svg {...props}><path d="M5 12h14M12 5l7 7-7 7" /></svg>,
    eye: <svg {...props}><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8Z" /><circle cx="12" cy="12" r="3" /></svg>,
    download: <svg {...props}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M7 10l5 5 5-5M12 15V3" /></svg>,
    refresh: <svg {...props}><path d="M21 12a9 9 0 0 1-15.6 6.1M3 12A9 9 0 0 1 18.6 5.9M3 18v-6h6M21 6v6h-6" /></svg>,
    doc: <svg {...props}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6M8 13h8M8 17h6" /></svg>,
    document: <svg {...props}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6M8 13h8M8 17h8" /></svg>,
    file: <svg {...props}><path d="M14 2H7a2 2 0 0 0-2 2v16h14V7Z" /><path d="M14 2v5h5M8 12h8M8 16h6" /></svg>,
    cube: <svg {...props}><path d="m21 16-9 5-9-5V8l9-5 9 5v8Z" /><path d="m3.3 7.8 8.7 5 8.7-5M12 22v-9" /></svg>,
    rocket: <svg {...filled}><path d="M13 3c4.7.5 7.5 3.3 8 8l-5 5-6-6 3-7ZM6 14l4 4-4 3-3-3 3-4Zm4-4-5 1-3 5 6-2 2-4Zm4 4-1 5-5 3 2-6 4-2Z" /></svg>,
    flow: <svg {...props}><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="9" y="15" width="6" height="6" rx="1" /><path d="M7 10v2.5h5V15M17 10v2.5h-5" /></svg>,
    checkfile: <svg {...props}><path d="M14 2H6a2 2 0 0 0-2 2v16h14V8Z" /><path d="M14 2v6h6M8 15l2 2 5-5" /></svg>,
    shield: <svg {...filled}><path d="M12 2 20 5v6c0 5-3.4 9.4-8 11-4.6-1.6-8-6-8-11V5l8-3Zm-1 13.5 6-6-1.4-1.4L11 12.7 8.4 10.1 7 11.5l4 4Z" /></svg>,
    cloud: <svg {...filled}><path d="M19 18H7a5 5 0 0 1-.7-10A6.5 6.5 0 0 1 19 10.5 3.8 3.8 0 0 1 19 18Zm-8-7-4 4h3v3h2v-3h3l-4-4Z" /></svg>,
    sync: <svg {...props}><path d="M21 7v6h-6M3 17v-6h6" /><path d="M21 13A8 8 0 0 0 7.5 7.1L3 11M3 11a8 8 0 0 0 13.5 5.9L21 13" /></svg>,
    history: <svg {...props}><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5M12 7v5l3 2" /></svg>,
    alert: <svg {...props}><path d="M10.5 17.5h3M12 3v11" /><path d="M12 2l10.35 17.5H1.65L12 2Z" /></svg>,
    bot: <svg {...props}><rect x="5" y="8" width="14" height="10" rx="3" /><path d="M12 8V4M8 12h.01M16 12h.01M9 18l-2 3M15 18l2 3" /></svg>,
    plus: <svg {...props}><path d="M12 5v14M5 12h14" /></svg>
  };

  return icons[name] ?? icons.doc;
}
