import { lazy, Suspense, useMemo } from 'react';
import { useTheme, usePrefersReducedMotion } from '@/hooks/useTheme';
import type { HarnessComponent, HomeData } from '@/lib/api/types';
import { readPalette } from './palette';
import { SceneBoundary, webglAvailable } from './SceneBoundary';

const DioramaImpl = lazy(() => import('./CommonsDiorama'));
const AssemblyImpl = lazy(() => import('./HarnessAssembly'));

function usePalette() {
  const { theme } = useTheme();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useMemo(() => readPalette(theme === 'dark'), [theme]);
}

const Placeholder = ({ label }: { label: string }) => (
  <div className="grid h-full w-full place-items-center">
    <span className="font-mono text-xs text-muted">{label}</span>
  </div>
);

export function Diorama({ data, onSelect }: { data: HomeData; onSelect: (to: string) => void }) {
  const p = usePalette();
  const reduced = usePrefersReducedMotion();
  const ok = useMemo(webglAvailable, []);
  if (!ok) return <Placeholder label="3D view needs WebGL. Everything shown here is listed below." />;
  return (
    <SceneBoundary fallback={<Placeholder label="The 3D view couldn't start. Everything shown here is listed below." />}>
      <Suspense fallback={<Placeholder label="Building the board…" />}>
        <DioramaImpl key={String(p.dark)} data={data} p={p} reduced={reduced} onSelect={onSelect} />
      </Suspense>
    </SceneBoundary>
  );
}

export function Assembly({ components }: { components: HarnessComponent[] }) {
  const p = usePalette();
  const reduced = usePrefersReducedMotion();
  const ok = useMemo(webglAvailable, []);
  if (!ok) return null;
  return (
    <SceneBoundary fallback={null}>
      <Suspense fallback={<Placeholder label="Assembling…" />}>
        <AssemblyImpl key={String(p.dark)} components={components} p={p} reduced={reduced} />
      </Suspense>
    </SceneBoundary>
  );
}
