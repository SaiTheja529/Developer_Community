/**
 * The Commons: an isometric paper model of the community, built from /api/home.
 *
 * Encoding (also explained in the legend beside the canvas):
 *   Harness Lab   → towers; floors grow with votes and GitHub stars. Featured towers wear a white cap.
 *   Project Ideas → beacons; the lantern glows when the idea is looking for collaborators.
 *   Knowledge Hub → book stacks (one book per recommendation, up to 6) and shelves (one spine per resource).
 *   AI Workspace  → the faceted core with a dashed orbit; dashed threads reach every district,
 *                   because "Ask AI" works from any page. Dashed = AI, everywhere in the product.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber';
import { Line, OrbitControls, OrthographicCamera, RoundedBox } from '@react-three/drei';
import { Projector, useAnchors, type Vec3 } from './Overlay';
import * as THREE from 'three';
import type { CollectionSummary, HarnessSummary, HomeData, IdeaSummary, ResourceSummary } from '@/lib/api/types';
import { hash01, mix, type Palette } from './palette';

type Kind = 'harness' | 'idea' | 'resource' | 'collection' | 'ai';
interface Pick { key: string; kind: Kind; title: string; meta: string; to: string; pos: [number, number, number]; top: number }

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
const dedupe = <T extends { id: string }>(lists: T[][], n: number) => {
  const seen = new Set<string>();
  const out: T[] = [];
  for (const l of lists) for (const x of l) if (!seen.has(x.id) && out.length < n) { seen.add(x.id); out.push(x); }
  return out;
};

/* ── Layout (world units; board top is y = 0) ─────────────────────────── */
const HARNESS_PLATE = { x: -4.3, z: -1.9, w: 6.2, d: 4.6 };
const IDEA_PLATE = { x: 4.3, z: -1.9, w: 6.2, d: 4.6 };
const KNOW_PLATE = { x: 0, z: 2.95, w: 14.8, d: 3.3 };
const AI_POS: [number, number, number] = [0, 3.1, -1.9];
const grid3 = (cx: number, cz: number) =>
  [-1, 0, 1].flatMap((r) => [-1, 0, 1].map((c) => [cx + c * 1.8, cz + r * 1.4] as [number, number]));
const HARNESS_SLOTS = grid3(HARNESS_PLATE.x, HARNESS_PLATE.z);
const IDEA_SLOTS = grid3(IDEA_PLATE.x, IDEA_PLATE.z);
const RESOURCE_SLOTS = [2.2, 3.65].flatMap((z) => [-6.4, -4.9, -3.4, -1.9].map((x) => [x, z] as [number, number]));
const SHELF_SLOTS: [number, number][] = [[1.9, 2.2], [4.9, 2.2], [1.9, 3.65], [4.9, 3.65]];

/* ── Motion helpers ───────────────────────────────────────────────────── */
function Grow({ delay, reduced, children }: { delay: number; reduced: boolean; children: React.ReactNode }) {
  const ref = useRef<THREE.Group>(null);
  const t0 = useRef<number | null>(null);
  useFrame(({ clock }) => {
    const g = ref.current;
    if (!g) return;
    if (reduced) { g.scale.y = 1; return; }
    t0.current ??= clock.elapsedTime;
    const t = clamp((clock.elapsedTime - t0.current - delay) / 0.7, 0, 1);
    g.scale.y = Math.max(0.0001, 1 - Math.pow(1 - t, 3));
  });
  return <group ref={ref} scale={[1, reduced ? 1 : 0.0001, 1]}>{children}</group>;
}

function Lift({ on, children }: { on: boolean; children: React.ReactNode }) {
  const ref = useRef<THREE.Group>(null);
  useFrame((_, dt) => {
    if (ref.current) ref.current.position.y = THREE.MathUtils.damp(ref.current.position.y, on ? 0.22 : 0, 12, dt);
  });
  return <group ref={ref}>{children}</group>;
}

/* ── Pieces ───────────────────────────────────────────────────────────── */
function Paper({ color, emissive, intensity = 0, flat = false }: { color: string; emissive?: string; intensity?: number; flat?: boolean }) {
  return <meshStandardMaterial color={color} roughness={0.88} metalness={0} emissive={emissive ?? '#000000'} emissiveIntensity={intensity} flatShading={flat} />;
}

function Tower({ h, p, hot }: { h: HarnessSummary; p: Palette; hot: boolean }) {
  const score = Math.log2(1 + h.counts.votes) * 1.1 + Math.log10(1 + (h.repo.stars ?? 0)) * 0.9;
  const floors = clamp(Math.round(2 + score), 2, 10);
  const slab = mix(p.harness, p.dark ? p.board : '#ffffff', p.dark ? 0.15 : 0.4);
  const core = mix(p.harness, '#000000', p.dark ? 0.35 : 0.1);
  const H = floors * 0.3;
  return (
    <group>
      <mesh position={[0, H / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[0.66, H, 0.66]} />
        <Paper color={core} />
      </mesh>
      {Array.from({ length: floors }, (_, i) => (
        <mesh key={i} position={[0, 0.15 + i * 0.3, 0]} castShadow receiveShadow>
          <boxGeometry args={[0.9, 0.22, 0.9]} />
          <Paper color={hot ? mix(slab, p.harness, 0.35) : slab} />
        </mesh>
      ))}
      {h.is_featured && (
        <mesh position={[0, H + 0.12, 0]} castShadow>
          <cylinderGeometry args={[0.001, 0.36, 0.36, 4]} />
          <Paper color={p.dark ? '#e8eaed' : '#ffffff'} flat />
        </mesh>
      )}
    </group>
  );
}

function Beacon({ i, p, reduced, hot }: { i: IdeaSummary; p: Palette; reduced: boolean; hot: boolean }) {
  const seeking = i.collaboration_status === 'seeking_collaborators';
  const ph = clamp(0.45 + Math.log2(1 + i.counts.votes + i.counts.interest) * 0.32, 0.45, 2.2);
  const lantern = useRef<THREE.Mesh>(null);
  const mat = useRef<THREE.MeshStandardMaterial>(null);
  const phase = hash01(i.id) * Math.PI * 2;
  useFrame(({ clock }) => {
    const t = clock.elapsedTime + phase;
    if (lantern.current && !reduced) {
      lantern.current.position.y = ph + 0.5 + Math.sin(t * 1.4) * 0.06;
      lantern.current.rotation.y = t * 0.4;
    }
    if (mat.current) mat.current.emissiveIntensity = seeking ? (reduced ? 0.55 : 0.4 + Math.sin(t * 2.2) * 0.25) : 0;
  });
  const soft = mix(p.idea, p.dark ? p.board : '#ffffff', p.dark ? 0.2 : 0.45);
  return (
    <group>
      <mesh position={[0, ph / 2, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.3, 0.42, ph, 6]} />
        <Paper color={hot ? mix(soft, p.idea, 0.3) : soft} flat />
      </mesh>
      <mesh ref={lantern} position={[0, ph + 0.5, 0]} castShadow>
        <icosahedronGeometry args={[0.32, 0]} />
        <meshStandardMaterial ref={mat} color={seeking ? p.idea : mix(p.idea, p.muted, 0.5)} emissive={p.idea} roughness={0.6} flatShading />
      </mesh>
      {seeking && (
        <mesh rotation-x={-Math.PI / 2} position={[0, 0.012, 0]}>
          <ringGeometry args={[0.55, 0.62, 40]} />
          <meshBasicMaterial color={p.idea} transparent opacity={0.7} />
        </mesh>
      )}
    </group>
  );
}

function BookStack({ r, p, hot }: { r: ResourceSummary; p: Palette; hot: boolean }) {
  const n = clamp(1 + r.counts.votes, 1, 6);
  const broken = r.link.status === 'broken' || r.link.status === 'unreachable' || r.link.open_reports > 0;
  const tints = [p.knowledge, mix(p.knowledge, '#ffffff', 0.45), mix(p.knowledge, p.board, 0.25), mix(p.knowledge, '#ffffff', 0.25)];
  return (
    <group rotation={[0, 0, broken ? 0.18 : 0]}>
      {Array.from({ length: n }, (_, k) => {
        const w = 0.78 + hash01(r.id, k) * 0.2;
        const color = broken ? mix(tints[k % 4], p.muted, 0.6) : hot ? mix(tints[k % 4], p.knowledge, 0.3) : tints[k % 4];
        return (
          <mesh key={k} position={[0, 0.075 + k * 0.155, 0]} rotation={[0, (hash01(r.id, k + 9) - 0.5) * 0.45, 0]} castShadow receiveShadow>
            <boxGeometry args={[w, 0.14, 0.6]} />
            <Paper color={color} />
          </mesh>
        );
      })}
      {r.resource_type === 'official_docs' && r.official_verified && (
        <mesh position={[0.22, n * 0.155 - 0.06, 0.31]} castShadow>
          <boxGeometry args={[0.09, 0.22, 0.02]} />
          <Paper color={p.success} />
        </mesh>
      )}
    </group>
  );
}

function Shelf({ c, p, hot }: { c: CollectionSummary; p: Palette; hot: boolean }) {
  const n = clamp(c.counts.items, 0, 10);
  const wood = p.dark ? mix(p.board, '#ffffff', 0.12) : mix(p.board, '#000000', 0.06);
  return (
    <group>
      <mesh position={[0, 0.04, 0]} castShadow receiveShadow><boxGeometry args={[1.75, 0.08, 0.55]} /><Paper color={wood} /></mesh>
      <mesh position={[0, 0.98, 0]} castShadow receiveShadow><boxGeometry args={[1.75, 0.06, 0.55]} /><Paper color={wood} /></mesh>
      {[-0.85, 0.85].map((x) => (
        <mesh key={x} position={[x, 0.5, 0]} castShadow receiveShadow><boxGeometry args={[0.06, 0.94, 0.55]} /><Paper color={wood} /></mesh>
      ))}
      <mesh position={[0, 0.5, -0.25]} receiveShadow><boxGeometry args={[1.65, 0.9, 0.03]} /><Paper color={mix(wood, p.knowledge, 0.08)} /></mesh>
      {Array.from({ length: n }, (_, k) => {
        const h = 0.5 + hash01(c.id, k) * 0.3;
        const last = k === n - 1 && n < 10;
        return (
          <mesh key={k} position={[-0.72 + k * 0.145 + (last ? 0.05 : 0), 0.08 + h / 2, 0.02]} rotation={[0, 0, last ? -0.28 : 0]} castShadow>
            <boxGeometry args={[0.12, h, 0.42]} />
            <Paper color={k % 3 === 0 ? p.knowledge : mix(p.knowledge, hot ? p.knowledge : '#ffffff', 0.2 + (k % 3) * 0.2)} />
          </mesh>
        );
      })}
    </group>
  );
}

function EmptyLot({ x, z, p }: { x: number; z: number; p: Palette }) {
  const s = 0.42;
  const pts: [number, number, number][] = [[-s, 0, -s], [s, 0, -s], [s, 0, s], [-s, 0, s], [-s, 0, -s]];
  return <Line points={pts} position={[x, 0.11, z]} color={p.muted} lineWidth={1} transparent opacity={0.45} />;
}

function AICore({ p, reduced, hot }: { p: Palette; reduced: boolean; hot: boolean }) {
  const gem = useRef<THREE.Mesh>(null);
  const ring = useRef<THREE.Group>(null);
  const orb = useRef<THREE.Mesh>(null);
  const circle = useMemo(() => Array.from({ length: 65 }, (_, i) => {
    const a = (i / 64) * Math.PI * 2;
    return [Math.cos(a) * 1.15, 0, Math.sin(a) * 1.15] as [number, number, number];
  }), []);
  useFrame(({ clock }, dt) => {
    if (reduced) return;
    const t = clock.elapsedTime;
    if (gem.current) { gem.current.rotation.y += dt * (hot ? 1.2 : 0.35); gem.current.position.y = Math.sin(t * 1.1) * 0.08; }
    if (ring.current) ring.current.rotation.y = -t * 0.25;
    if (orb.current) { const a = t * 0.9; orb.current.position.set(Math.cos(a) * 1.15, 0, Math.sin(a) * 1.15); }
  });
  return (
    <group position={AI_POS}>
      <mesh ref={gem} castShadow>
        <octahedronGeometry args={[0.6, 0]} />
        <meshStandardMaterial color={mix(p.ai, '#ffffff', p.dark ? 0.1 : 0.35)} emissive={p.ai} emissiveIntensity={hot ? 0.5 : 0.18} roughness={0.5} flatShading />
      </mesh>
      <group rotation={[0.42, 0, 0.12]}>
        <group ref={ring}>
          <Line points={circle} color={p.ai} lineWidth={1.6} dashed dashSize={0.16} gapSize={0.11} />
          <mesh ref={orb} position={[1.15, 0, 0]}>
            <sphereGeometry args={[0.08, 16, 16]} />
            <meshBasicMaterial color={p.ai} />
          </mesh>
        </group>
      </group>
    </group>
  );
}

function Threads({ p }: { p: Palette }) {
  const ends: [number, number, number][] = [[-1.6, 0.12, -1.9], [1.6, 0.12, -1.9], [0, 0.12, 1.4], [0, 0.12, -1.9]];
  return (
    <>
      {ends.map((e, i) => (
        <Line key={i} points={[[AI_POS[0], AI_POS[1] - 0.6, AI_POS[2]], e]} color={p.ai} lineWidth={1} dashed dashSize={0.12} gapSize={0.12} transparent opacity={0.55} />
      ))}
    </>
  );
}

function BoardDots({ p }: { p: Palette }) {
  const geo = useMemo(() => {
    const pts: number[] = [];
    for (let x = -7.8; x <= 7.8; x += 0.5) for (let z = -4.4; z <= 4.7; z += 0.5) pts.push(x, 0.002, z);
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    return g;
  }, []);
  return (
    <points geometry={geo}>
      <pointsMaterial color={p.muted} size={1.6} sizeAttenuation={false} transparent opacity={p.dark ? 0.35 : 0.3} />
    </points>
  );
}

function Plate({ x, z, w, d, color }: { x: number; z: number; w: number; d: number; color: string }) {
  return (
    <RoundedBox args={[w, 0.1, d]} radius={0.04} smoothness={2} position={[x, 0.05, z]} receiveShadow>
      <Paper color={color} />
    </RoundedBox>
  );
}

/* ── Camera fit ───────────────────────────────────────────────────────── */
function FitCamera() {
  const { size, camera } = useThree();
  useEffect(() => {
    const cam = camera as THREE.OrthographicCamera;
    cam.zoom = Math.min(size.width / 19.5, size.height / 12.2);
    cam.updateProjectionMatrix();
  }, [size, camera]);
  return null;
}

/* ── Scene ────────────────────────────────────────────────────────────── */
interface SceneProps {
  data: HomeData; p: Palette; reduced: boolean; onSelect: (to: string) => void; coarse: boolean;
  hover: Pick | null; setHover: React.Dispatch<React.SetStateAction<Pick | null>>;
  anchors: ReturnType<typeof useAnchors>['anchors'];
}
function Scene({ data, p, reduced, onSelect, coarse, hover, setHover, anchors }: SceneProps) {
  const harnesses = dedupe([data.harnesses.featured, data.harnesses.trending, data.harnesses.recent], 9);
  const ideas = dedupe([data.ideas.featured, data.ideas.trending, data.ideas.recent], 9);
  const resources = dedupe([data.resources.featured, data.resources.trending, data.resources.recent], 8);
  const collections = dedupe([data.collections.featured, data.collections.trending, data.collections.recent], 4);

  const bind = (pick: Pick) => ({
    onPointerOver: (e: ThreeEvent<PointerEvent>) => {
      e.stopPropagation();
      setHover(pick);
      document.body.style.cursor = 'pointer';
    },
    onPointerOut: () => {
      setHover((h) => (h?.key === pick.key ? null : h));
      document.body.style.cursor = '';
    },
    onClick: (e: ThreeEvent<MouseEvent>) => {
      e.stopPropagation();
      // On touch, the first tap previews and the second opens.
      if (coarse && hover?.key !== pick.key) { setHover(pick); return; }
      document.body.style.cursor = '';
      onSelect(pick.to);
    },
  });
  useEffect(() => () => { document.body.style.cursor = ''; }, []);

  let order = 0;
  const delay = () => 0.15 + order++ * 0.055;
  const hit = (k: string) => hover?.key === k;

  const harnessColor = mix(p.harness, p.board, p.dark ? 0.82 : 0.86);
  const ideaColor = mix(p.idea, p.board, p.dark ? 0.82 : 0.86);
  const knowColor = mix(p.knowledge, p.board, p.dark ? 0.82 : 0.88);

  return (
    <>
      <FitCamera />
      <hemisphereLight args={[p.dark ? '#9aa6c0' : '#ffffff', p.dark ? '#0e1013' : '#d9d6cb', p.dark ? 0.9 : 1.15]} />
      <directionalLight
        position={[7, 14, 9]}
        intensity={p.dark ? 1.4 : 1.8}
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-left={-12}
        shadow-camera-right={12}
        shadow-camera-top={12}
        shadow-camera-bottom={-12}
        shadow-bias={-0.0004}
      />

      {/* Board */}
      <RoundedBox args={[16.4, 0.5, 9.7]} radius={0.12} smoothness={3} position={[0, -0.25, 0.2]} receiveShadow>
        <Paper color={p.board} />
      </RoundedBox>
      <mesh position={[0, -0.62, 0.2]} receiveShadow>
        <boxGeometry args={[16.0, 0.25, 9.3]} />
        <Paper color={p.boardEdge} />
      </mesh>
      <BoardDots p={p} />

      <Plate {...HARNESS_PLATE} color={harnessColor} />
      <Plate {...IDEA_PLATE} color={ideaColor} />
      <Plate {...KNOW_PLATE} color={knowColor} />
      <mesh position={[0, 0.03, -1.9]} receiveShadow>
        <cylinderGeometry args={[0.8, 0.8, 0.06, 6]} />
        <Paper color={mix(p.ai, p.board, 0.8)} />
      </mesh>

      <Projector anchors={anchors} />

      {/* Harness towers */}
      {HARNESS_SLOTS.map(([x, z], idx) => {
        const h = harnesses[idx];
        if (!h) return <EmptyLot key={`hl${idx}`} x={x} z={z} p={p} />;
        const floors = clamp(Math.round(2 + Math.log2(1 + h.counts.votes) * 1.1 + Math.log10(1 + (h.repo.stars ?? 0)) * 0.9), 2, 10);
        const pick: Pick = { key: h.id, kind: 'harness', title: h.name, meta: `${h.repo.owner}/${h.repo.name} · ▲ ${h.counts.votes} · ★ ${h.repo.stars ?? 0}`, to: `/harnesses/${h.id}/${h.slug}`, pos: [x, 0.1, z], top: floors * 0.3 + 0.5 };
        return (
          <group key={h.id} position={[x, 0.1, z]} {...bind(pick)}>
            <Lift on={hit(h.id)}><Grow delay={delay()} reduced={reduced}><Tower h={h} p={p} hot={hit(h.id)} /></Grow></Lift>
          </group>
        );
      })}

      {/* Idea beacons */}
      {IDEA_SLOTS.map(([x, z], idx) => {
        const it = ideas[idx];
        if (!it) return <EmptyLot key={`il${idx}`} x={x} z={z} p={p} />;
        const status = it.collaboration_status === 'seeking_collaborators' ? 'looking for collaborators' : it.collaboration_status === 'team_formed' ? 'team formed' : 'sharing';
        const pick: Pick = { key: it.id, kind: 'idea', title: it.title, meta: `${status} · ▲ ${it.counts.votes} · ✋ ${it.counts.interest}`, to: `/ideas/${it.id}/${it.slug}`, pos: [x, 0.1, z], top: 2.2 };
        return (
          <group key={it.id} position={[x, 0.1, z]} {...bind(pick)}>
            <Lift on={hit(it.id)}><Grow delay={delay()} reduced={reduced}><Beacon i={it} p={p} reduced={reduced} hot={hit(it.id)} /></Grow></Lift>
          </group>
        );
      })}

      {/* Resource stacks */}
      {RESOURCE_SLOTS.map(([x, z], idx) => {
        const r = resources[idx];
        if (!r) return <EmptyLot key={`rl${idx}`} x={x} z={z} p={p} />;
        const pick: Pick = { key: r.id, kind: 'resource', title: r.name, meta: `${r.domain} · ▲ ${r.counts.votes}${r.official_verified && r.resource_type === 'official_docs' ? ' · official' : ''}`, to: `/resources/${r.id}`, pos: [x, 0.1, z], top: 1.4 };
        return (
          <group key={r.id} position={[x, 0.1, z]} {...bind(pick)}>
            <Lift on={hit(r.id)}><Grow delay={delay()} reduced={reduced}><BookStack r={r} p={p} hot={hit(r.id)} /></Grow></Lift>
          </group>
        );
      })}

      {/* Collection shelves */}
      {SHELF_SLOTS.map(([x, z], idx) => {
        const c = collections[idx];
        if (!c) return <EmptyLot key={`cl${idx}`} x={x} z={z} p={p} />;
        const pick: Pick = { key: c.id, kind: 'collection', title: c.title, meta: `${c.counts.items} resources · ▲ ${c.counts.votes}`, to: `/collections/${c.id}/${c.slug}`, pos: [x, 0.1, z], top: 1.5 };
        return (
          <group key={c.id} position={[x, 0.1, z]} {...bind(pick)}>
            <Lift on={hit(c.id)}><Grow delay={delay()} reduced={reduced}><Shelf c={c} p={p} hot={hit(c.id)} /></Grow></Lift>
          </group>
        );
      })}

      {/* AI */}
      <Threads p={p} />
      <group {...bind({ key: 'ai', kind: 'ai', title: 'AI Workspace', meta: 'Ask · Generate · Refine', to: '/ai', pos: [AI_POS[0], AI_POS[1] - 1.2, AI_POS[2]], top: 2 })}>
        <AICore p={p} reduced={reduced} hot={hit('ai')} />
      </group>

    </>
  );
}

const LABELS = (p: Palette, d: HomeData): { key: string; pos: Vec3; color: string; name: string; count: number }[] => [
  { key: 'l-h', pos: [HARNESS_PLATE.x, 0.15, HARNESS_PLATE.z + HARNESS_PLATE.d / 2 + 0.05], color: p.harness, name: 'Harness Lab', count: d.counts.harnesses },
  { key: 'l-i', pos: [IDEA_PLATE.x, 0.15, IDEA_PLATE.z + IDEA_PLATE.d / 2 + 0.05], color: p.idea, name: 'Project Ideas', count: d.counts.ideas },
  { key: 'l-r', pos: [KNOW_PLATE.x - 3, 0.15, KNOW_PLATE.z + KNOW_PLATE.d / 2 + 0.05], color: p.knowledge, name: 'Knowledge Hub', count: d.counts.resources },
  { key: 'l-c', pos: [KNOW_PLATE.x + 3.4, 0.15, KNOW_PLATE.z + KNOW_PLATE.d / 2 + 0.05], color: p.knowledge, name: 'Collections', count: d.counts.collections },
];

export default function CommonsDiorama({ data, p, reduced, onSelect }: { data: HomeData; p: Palette; reduced: boolean; onSelect: (to: string) => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(true);
  const [hover, setHover] = useState<Pick | null>(null);
  const { anchors, anchor } = useAnchors();
  const coarse = useMemo(() => window.matchMedia('(pointer: coarse)').matches, []);
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { threshold: 0.01 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  const accent = hover && (hover.kind === 'harness' ? p.harness : hover.kind === 'idea' ? p.idea : p.knowledge);

  return (
    <div ref={wrap} className="relative h-full w-full">
      <Canvas
        shadows="percentage"
        flat
        dpr={[1, 2]}
        frameloop={visible ? 'always' : 'never'}
        gl={{ antialias: true, alpha: true }}
        onPointerMissed={() => { document.body.style.cursor = ''; setHover(null); }}
      >
        <OrthographicCamera makeDefault position={[12, 11.5, 13]} near={0.1} far={100} />
        <OrbitControls
          target={[0, 0.4, 0.2]}
          enableZoom={false}
          enablePan={false}
          enableRotate={!coarse}
          enableDamping
          dampingFactor={0.08}
          minPolarAngle={0.7}
          maxPolarAngle={1.1}
          minAzimuthAngle={Math.atan2(12, 13) - 0.65}
          maxAzimuthAngle={Math.atan2(12, 13) + 0.65}
          rotateSpeed={0.5}
        />
        <Scene data={data} p={p} reduced={reduced} onSelect={onSelect} coarse={coarse} hover={hover} setHover={setHover} anchors={anchors} />
      </Canvas>
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        {LABELS(p, data).map((l) => (
          <div key={l.key} ref={anchor(l.key, l.pos)} className="invisible absolute top-0 left-0 flex items-center gap-1.5 whitespace-nowrap rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-medium shadow-[var(--shadow-card)]">
            <span className="size-2 rounded-full" style={{ background: l.color }} />
            {l.name}
            <span className="font-mono text-muted">{l.count}</span>
          </div>
        ))}
        {hover && (
          <div
            ref={anchor('tip', [hover.pos[0], hover.pos[1] + hover.top, hover.pos[2]])}
            className="invisible absolute top-0 left-0 z-10 w-max max-w-[240px] rounded-[10px] bg-surface px-3 py-2 shadow-[var(--shadow-dialog)]"
            style={hover.kind === 'ai' ? { border: `1.5px dashed ${p.ai}` } : { border: '1px solid var(--border)', borderTop: `3px solid ${accent}` }}
          >
            <p className="text-sm leading-snug font-semibold">{hover.title}</p>
            <p className="mt-0.5 font-mono text-[11px] text-muted">{hover.meta}</p>
            <p className="mt-1 text-[11px] text-muted">{coarse ? 'Tap again to open' : 'Click to open'}</p>
          </div>
        )}
      </div>
    </div>
  );
}
