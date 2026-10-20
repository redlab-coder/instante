'use strict';
// Local vector family: crop corners, nested cuts and consistent rounded strokes.
const PolaroidEditorIcons=(()=>{
  const paths={
    'clear-all':'<rect x="6" y="6" width="15" height="15" rx="3"/><path d="M16 3H6a3 3 0 0 0-3 3v10m7-6 7 7m-7 0 7-7"/>',
    folder:'<path d="M3 7h7l2 2h9v11H3zM3 7V4h7l2 3"/>',
    save:'<path d="M5 3h12l4 4v14H3V3h2zm2 0v6h10V3M7 21v-8h10v8"/>',
    portrait:'<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M8 5h8v9H8zm1 13h6"/>',
    print:'<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M5 8h8v8H5zm12-3v14"/>',
    grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    invert:'<path d="M4 8a8 8 0 0 1 14-2l2 2m0-5v5h-5M20 16a8 8 0 0 1-14 2l-2-2m0 5v-5h5"/>',
    check:'<path d="m5 12 4 4L19 6"/>',

    update:'<path d="M4.6 8a8 8 0 1 1-.3 7M4 3v5h5m3 0v8m-3-3 3 3 3-3"/>',
    brand:'<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M8 5h8v9H8zm1 13h6"/>' ,
    square:'<rect x="3" y="3" width="18" height="18" rx="4" stroke-dasharray="2.5 2.5"/><rect x="6.5" y="6.5" width="11" height="11" rx="2"/>',
    round_g:'<circle cx="12" cy="12" r="9" stroke-dasharray="2.5 2.5"/><circle cx="12" cy="12" r="6.5"/>',
    round_m:'<circle cx="12" cy="12" r="7.6" stroke-dasharray="2.5 2.5"/><circle cx="12" cy="12" r="5"/>',
    round_p:'<circle cx="12" cy="12" r="6.2" stroke-dasharray="2.5 2.5"/><circle cx="12" cy="12" r="3.6"/>',
    help:'<circle cx="12" cy="12" r="9"/><path d="M9.6 9a2.5 2.5 0 0 1 4.8.8c0 1.8-2.4 2-2.4 3.6m0 3.1h.01"/>',
    power:'<path d="M12 3v8m-5.5-6a8 8 0 1 0 11 0"/>',
    export:'<path d="M14 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7"/><circle cx="8.5" cy="13" r="2"/><circle cx="14.5" cy="13" r="2"/><path d="M15 4h5v5m0-5-7 7"/>',
    'download-sheet':'<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M12 7v7m-3-3 3 3 3-3M8 17h8"/>',
    add:'<path d="M12 5v14M5 12h14"/>',
    'add-photo':'<rect x="3" y="4" width="17" height="17" rx="4"/><path d="m4 17 5-5 4 4 3-2m1-13v6m-3-3h6"/><circle cx="8" cy="9" r="1"/>',
    guides:'<circle cx="12" cy="12" r="8.5" stroke-dasharray="2.2 2.2"/><circle cx="12" cy="12" r="5"/><path d="M12 1v3m0 16v3M1 12h3m16 0h3"/>',
    center:'<path d="M3 8V4a1 1 0 0 1 1-1h4m8 0h4a1 1 0 0 1 1 1v4m0 8v4a1 1 0 0 1-1 1h-4m-8 0H4a1 1 0 0 1-1-1v-4m9-9v10m-5-5h10"/>',
    rotate:'<path d="M4 8a8 8 0 1 1-1 8M4 3v5h5"/><rect x="8.5" y="8.5" width="7" height="7" rx="1.5"/>',
    reset:'<path d="M4 9a8 8 0 1 1 0 6M4 4v5h5m3-1v4l3 2"/>',
    retry:'<path d="M4 8a8 8 0 0 1 14-3l2 3m0-5v5h-5M20 16A8 8 0 0 1 6 19l-2-3m0 5v-5h5"/>',
    close:'<path d="m6 6 12 12M6 18 18 6"/>',up:'<path d="m6 14 6-6 6 6"/>',down:'<path d="m6 10 6 6 6-6"/>',
    remove:'<path d="M4 6h16M9 6V3h6v3M6 6l1 14h10l1-14M10 10v6m4-6v6"/>',
    zoom:'<circle cx="10" cy="10" r="6.5"/><path d="m15 15 5.5 5.5M10 7v6m-3-3h6"/>',
    brightness:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
    contrast:'<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5v17a8.5 8.5 0 0 0 0-17" fill="currentColor" stroke="none"/>',
    saturation:'<path d="M12 3c2.8 4 6.5 7.3 6.5 11a6.5 6.5 0 0 1-13 0C5.5 10.3 9.2 7 12 3Z"/><path d="M9 14a3 3 0 0 0 3 3"/>',
    sharpness:'<path d="m12 3 9 17H3L12 3Z"/><path d="m12 8 5 9H7l5-9Z"/>',
  };
  const svg=name=>`<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${paths[name]||paths.brand}</svg>`;
  const mount=(root=document)=>root.querySelectorAll('[data-icon]').forEach(el=>{el.innerHTML=svg(el.dataset.icon);});
  mount();return {svg,mount};
})();
