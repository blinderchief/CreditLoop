import { useEffect, useRef } from "react";

// A living "sea storm" gradient — drifting light through deep ocean water.
// Canvas so it feels like video, self-contained so it deploys anywhere.
// Palette: deep navy → ocean teal → storm cyan foam.
export function StormBg({ className = "" }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current!;
    const ctx = canvas.getContext("2d")!;
    let raf = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const blobs = [
      { hue: 190, x: 0.2, y: 0.3, r: 0.55, sx: 0.00008, sy: 0.00011, a: 0.55 },
      { hue: 175, x: 0.7, y: 0.6, r: 0.6, sx: -0.00010, sy: 0.00007, a: 0.5 },
      { hue: 205, x: 0.5, y: 0.15, r: 0.5, sx: 0.00006, sy: -0.00009, a: 0.45 },
      { hue: 168, x: 0.85, y: 0.35, r: 0.4, sx: -0.00007, sy: -0.00006, a: 0.4 },
    ];

    function resize() {
      canvas.width = canvas.clientWidth * dpr;
      canvas.height = canvas.clientHeight * dpr;
    }
    resize();
    window.addEventListener("resize", resize);

    function frame(t: number) {
      const w = canvas.width, h = canvas.height;
      // deep-ocean base
      const base = ctx.createLinearGradient(0, 0, 0, h);
      base.addColorStop(0, "#06131f");
      base.addColorStop(0.55, "#0a2233");
      base.addColorStop(1, "#0e3143");
      ctx.fillStyle = base;
      ctx.fillRect(0, 0, w, h);

      ctx.globalCompositeOperation = "lighter";
      for (const b of blobs) {
        const cx = (b.x + Math.sin(t * b.sx) * 0.12) * w;
        const cy = (b.y + Math.cos(t * b.sy) * 0.12) * h;
        const rad = b.r * Math.min(w, h);
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rad);
        g.addColorStop(0, `hsla(${b.hue}, 85%, 55%, ${b.a})`);
        g.addColorStop(0.5, `hsla(${b.hue}, 80%, 40%, ${b.a * 0.4})`);
        g.addColorStop(1, "hsla(200, 80%, 20%, 0)");
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, w, h);
      }
      ctx.globalCompositeOperation = "source-over";
      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={ref} className={`h-full w-full ${className}`} />;
}
