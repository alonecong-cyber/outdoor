/**
 * 等高线地形图背景：低透明度 SVG 波纹层，缓慢漂移。
 * 纯装饰，pointer-events 关闭，不挡交互。
 */
export function TopoBackdrop() {
  const rings = [140, 190, 240, 295, 355, 420];
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      <div className="topo-drift absolute -left-40 -top-32 h-[36rem] w-[36rem] opacity-[0.55]">
        <svg viewBox="0 0 800 800" className="h-full w-full" fill="none">
          {rings.map((r, i) => (
            <ellipse
              key={r}
              cx={400 + i * 14}
              cy={400 - i * 10}
              rx={r}
              ry={r * 0.82}
              stroke="#243126"
              strokeWidth={i === 0 ? 2 : 1}
            />
          ))}
        </svg>
      </div>
      <div className="topo-drift absolute -bottom-48 -right-40 h-[34rem] w-[34rem] opacity-[0.45]">
        <svg viewBox="0 0 800 800" className="h-full w-full" fill="none">
          {rings.map((r, i) => (
            <ellipse
              key={r}
              cx={400 - i * 12}
              cy={400 + i * 8}
              rx={r}
              ry={r * 0.7}
              stroke="#243126"
              strokeWidth={i === 0 ? 2 : 1}
            />
          ))}
        </svg>
      </div>
    </div>
  );
}
