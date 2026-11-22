/**
 * DOM overlays pinned to 3D points. drei's <Html> mounts a separate React root per overlay,
 * which races under React 19; here the overlays are ordinary DOM nodes rendered by the parent,
 * and a single useFrame projects each anchor to screen space and writes the transform.
 */
import { useCallback, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

export type Vec3 = [number, number, number];
type Pos = Vec3 | (() => Vec3);
type Anchor = { pos: Pos; el: HTMLElement };

export function useAnchors() {
  const anchors = useRef(new Map<string, Anchor>());
  /** Ref callback: React re-attaches it each render, so the latest position always wins. */
  const anchor = useCallback(
    (key: string, pos: Pos) => (el: HTMLElement | null) => {
      if (el) anchors.current.set(key, { pos, el });
      else anchors.current.delete(key);
    },
    [],
  );
  return { anchors, anchor };
}

const v = new THREE.Vector3();
export function Projector({ anchors }: { anchors: React.MutableRefObject<Map<string, Anchor>> }) {
  useFrame(({ camera, size }) => {
    for (const a of anchors.current.values()) {
      const q = typeof a.pos === 'function' ? a.pos() : a.pos;
      v.set(q[0], q[1], q[2]).project(camera);
      const x = (v.x * 0.5 + 0.5) * size.width;
      const y = (-v.y * 0.5 + 0.5) * size.height;
      a.el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) translate(-50%, -50%)`;
      a.el.style.visibility = 'visible';
    }
  });
  return null;
}
