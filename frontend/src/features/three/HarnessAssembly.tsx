/**
 * Exploded assembly of a harness: one layer per component type, stacked from
 * foundation (instruction files, rules) up to runtime (hooks, MCP servers, workflows).
 * The layers start collapsed and separate once, so you can see how the parts stack.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Edges, OrbitControls, OrthographicCamera } from '@react-three/drei';
import { Projector, useAnchors } from './Overlay';
import * as THREE from 'three';
import type { HarnessComponent } from '@/lib/api/types';
import { COMPONENT_LABELS } from '@/lib/modules';
import { mix, type Palette } from './palette';

const dims = (n: number) => {
  const cols = Math.min(4, n);
  const rows = Math.ceil(n / 4);
  return { cols, rows, w: Math.max(2.6, cols * 1.15 + 0.4), d: Math.max(1.6, rows * 0.9 + 0.5) };
};
const tile = (k: number, cols: number, rows: number): [number, number] => [(k % 4) * 1.15 - ((cols - 1) * 1.15) / 2, Math.floor(k / 4) * 0.9 - ((rows - 1) * 0.9) / 2];

const GAP = 1.3;

export const LAYER_ORDER = ['instruction_file', 'rule', 'agent', 'subagent', 'skill', 'slash_command', 'hook', 'mcp_server', 'workflow', 'other'];

function Layer({ index, total, items, p, reduced, active, setActive, ys, type }: {
  index: number; total: number; type: string; items: HarnessComponent[]; p: Palette; reduced: boolean;
  active: string | null; setActive: (k: string | null) => void; ys: React.MutableRefObject<number[]>;
}) {
  const ref = useRef<THREE.Group>(null);
  const gap = GAP;
  const target = index * gap;
  const t0 = useRef<number | null>(null);
  useFrame(({ clock }, dt) => {
    const g = ref.current;
    if (!g) return;
    if (reduced) { g.position.y = target; ys.current[index] = target; return; }
    t0.current ??= clock.elapsedTime;
    const t = clock.elapsedTime - t0.current;
    const want = t < 0.35 ? index * 0.14 : target;
    g.position.y = THREE.MathUtils.damp(g.position.y, want, 5, dt);
    ys.current[index] = g.position.y;
  });
  const shade = mix(p.harness, p.dark ? p.surface : '#ffffff', 0.25 + (index / Math.max(1, total - 1)) * 0.5);
  const { cols, rows, w, d } = dims(items.length);
  return (
    <group ref={ref} position={[0, reduced ? target : index * 0.14, 0]}>
      <mesh receiveShadow castShadow>
        <boxGeometry args={[w, 0.08, d]} />
        <meshStandardMaterial color={mix(p.surface, p.harness, p.dark ? 0.22 : 0.1)} roughness={0.9} />
        <Edges color={p.harness} />
      </mesh>
      {items.map((_c, k) => {
        const key = `${type}:${k}`;
        const on = active === key;
        const [x, z] = tile(k, cols, rows);
        return (
          <group key={key} position={[x, 0.2, z]}>
            <mesh
              castShadow
              onPointerOver={(e) => { e.stopPropagation(); setActive(key); document.body.style.cursor = 'pointer'; }}
              onPointerOut={() => { setActive(null); document.body.style.cursor = ''; }}
              onClick={(e) => { e.stopPropagation(); setActive(on ? null : key); }}
              position={[0, on ? 0.12 : 0, 0]}
            >
              <boxGeometry args={[0.95, 0.26, 0.7]} />
              <meshStandardMaterial color={on ? p.harness : shade} roughness={0.85} />
              <Edges color={mix(p.harness, '#000000', p.dark ? 0 : 0.3)} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

function Fit({ height }: { height: number }) {
  const { size, camera } = useThree();
  useEffect(() => {
    const cam = camera as THREE.OrthographicCamera;
    cam.zoom = Math.min(size.width / 6.5, size.height / (height + 1.5));
    cam.updateProjectionMatrix();
  }, [size, camera, height]);
  return null;
}

export default function HarnessAssembly({ components, p, reduced }: { components: HarnessComponent[]; p: Palette; reduced: boolean }) {
  const [active, setActive] = useState<string | null>(null);
  const ys = useRef<number[]>([]);
  const { anchors, anchor } = useAnchors();
  const layers = useMemo(() => {
    const by = new Map<string, HarnessComponent[]>();
    for (const c of components) by.set(c.type, [...(by.get(c.type) ?? []), c]);
    return LAYER_ORDER.filter((t) => by.has(t)).map((t) => ({ type: t, items: by.get(t)! }));
  }, [components]);
  const height = Math.max(0, layers.length - 1) * GAP + 0.4;
  const maxW = Math.max(...layers.map((l) => dims(l.items.length).w));
  useEffect(() => () => { document.body.style.cursor = ''; }, []);

  const activeInfo = (() => {
    if (!active) return null;
    const [type, ks] = active.split(':');
    const li = layers.findIndex((l) => l.type === type);
    const k = Number(ks);
    if (li < 0) return null;
    const { cols, rows } = dims(layers[li].items.length);
    const [x, z] = tile(k, cols, rows);
    return { c: layers[li].items[k], li, x, z };
  })();

  return (
    <div className="relative h-full w-full">
      <Canvas shadows="percentage" flat dpr={[1, 2]} gl={{ antialias: true, alpha: true }} onPointerMissed={() => setActive(null)}>
        <OrthographicCamera makeDefault position={[7, 6 + height / 2, 8]} near={0.1} far={100} />
        <Fit height={height} />
        <OrbitControls target={[0, height / 2, 0]} enableZoom={false} enablePan={false} enableDamping minPolarAngle={0.8} maxPolarAngle={1.25} rotateSpeed={0.5} />
        <hemisphereLight args={[p.dark ? '#9aa6c0' : '#ffffff', p.dark ? '#0e1013' : '#d9d6cb', p.dark ? 0.9 : 1.15]} />
        <directionalLight position={[5, 12, 7]} intensity={p.dark ? 1.3 : 1.7} castShadow shadow-mapSize={[1024, 1024]} shadow-camera-left={-6} shadow-camera-right={6} shadow-camera-top={8} shadow-camera-bottom={-6} shadow-bias={-0.0004} />
        {layers.map((l, i) => (
          <Layer key={l.type} index={i} total={layers.length} type={l.type} items={l.items} p={p} reduced={reduced} active={active} setActive={setActive} ys={ys} />
        ))}
        <Projector anchors={anchors} />
      </Canvas>
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        {layers.map((l, i) => (
          <span key={l.type} ref={anchor(`l-${l.type}`, () => [-maxW / 2 - 0.9, (ys.current[i] ?? 0) + 0.05, 0])} className="invisible absolute top-0 left-0 whitespace-nowrap font-mono text-[11px] text-muted">
            {COMPONENT_LABELS[l.type] ?? l.type} · {l.items.length}
          </span>
        ))}
        {activeInfo && (
          <div ref={anchor('tip', () => [activeInfo.x, (ys.current[activeInfo.li] ?? 0) + 1.0, activeInfo.z])} className="stripe-harness invisible absolute top-0 left-0 z-10 w-max max-w-[220px] rounded-[10px] border border-border bg-surface px-3 py-2 shadow-[var(--shadow-dialog)]">
            <p className="font-mono text-[13px] font-medium">{activeInfo.c.name}</p>
            <p className="mt-0.5 text-xs text-muted">{activeInfo.c.description}</p>
          </div>
        )}
      </div>
    </div>
  );
}
