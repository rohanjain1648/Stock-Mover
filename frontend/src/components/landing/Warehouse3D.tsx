/* Stock Mover digital twin: WH-KOL in the centre, the 20 stores on a ring around it,
   forklifts carrying cartons along today's real move routes. Inspired by OptiLogiX's warehouse3d. */
import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Text, ContactShadows } from "@react-three/drei";
import * as THREE from "three";

type StoreNode = { id: string; tier: string; util: number };

const STORES: StoreNode[] = [
  { id: "LKO-01", tier: "S++", util: 0.78 }, { id: "LKO-02", tier: "S+", util: 0.8 },
  { id: "LKO-03", tier: "A", util: 0.79 }, { id: "LKO-04", tier: "S+", util: 0.78 },
  { id: "KNP-01", tier: "S+", util: 0.83 }, { id: "KNP-02", tier: "A", util: 0.78 },
  { id: "KNP-03", tier: "B", util: 2.08 }, { id: "PAT-01", tier: "S++", util: 0.77 },
  { id: "PAT-02", tier: "S+", util: 0.78 }, { id: "PAT-03", tier: "A", util: 0.79 },
  { id: "PAT-04", tier: "B", util: 0.82 }, { id: "MZF-01", tier: "A", util: 0.37 },
  { id: "MZF-02", tier: "B", util: 0.83 }, { id: "BLR-01", tier: "S++", util: 0.88 },
  { id: "BLR-02", tier: "S++", util: 0.85 }, { id: "BLR-03", tier: "S+", util: 0.9 },
  { id: "BLR-04", tier: "S+", util: 0.83 }, { id: "BLR-05", tier: "B", util: 0.86 },
  { id: "MYS-01", tier: "A", util: 0.79 }, { id: "MYS-02", tier: "B", util: 0.89 },
];

// [from, to, colour] — headline moves from today's run
const ROUTES: [string, string, string][] = [
  ["KNP-03", "WH", "#c2410c"], ["WH", "LKO-01", "#d9641e"], ["WH", "MZF-01", "#d9641e"],
  ["WH", "PAT-01", "#2f6f6a"], ["WH", "BLR-01", "#2f6f6a"], ["WH", "BLR-02", "#2f6f6a"],
  ["KNP-03", "LKO-02", "#7a2e2e"], ["WH", "BLR-05", "#2f6f6a"], ["PAT-03", "WH", "#7a2e2e"],
];

const RADIUS = 9;
const pos = new Map<string, THREE.Vector3>([["WH", new THREE.Vector3(0, 0, 0)]]);
STORES.forEach((s, i) => {
  const a = (i / STORES.length) * Math.PI * 2;
  pos.set(s.id, new THREE.Vector3(Math.cos(a) * RADIUS, 0, Math.sin(a) * RADIUS));
});

const colourFor = (u: number) => (u > 1 ? "#dc2626" : u < 0.5 ? "#f59e0b" : "#2f6f6a");
const height = (tier: string) => ({ "S++": 2.4, "S+": 1.9, A: 1.5, B: 1.1 } as Record<string, number>)[tier];

function StoreRack({ s }: { s: StoreNode }) {
  const p = pos.get(s.id)!;
  const h = height(s.tier);
  const fill = Math.min(s.util, 1);
  const ref = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (ref.current && s.util > 1) ref.current.scale.y = 1 + Math.sin(clock.elapsedTime * 4) * 0.06;
  });
  return (
    <group position={p} rotation={[0, -Math.atan2(p.z, p.x) + Math.PI / 2, 0]}>
      <mesh position={[0, h / 2, 0]}>
        <boxGeometry args={[1.4, h, 1]} />
        <meshStandardMaterial color="#efe6d6" transparent opacity={0.35} />
      </mesh>
      <mesh ref={ref} position={[0, (h * fill) / 2, 0]}>
        <boxGeometry args={[1.2, h * fill, 0.8]} />
        <meshStandardMaterial color={colourFor(s.util)} />
      </mesh>
      {s.util > 1 && (
        <mesh position={[0, h + (h * (s.util - 1)) / 2, 0]}>
          <boxGeometry args={[1.2, h * (s.util - 1), 0.8]} />
          <meshStandardMaterial color="#dc2626" transparent opacity={0.55} />
        </mesh>
      )}
      <Text position={[0, h + (s.util > 1 ? h * (s.util - 1) : 0) + 0.45, 0]} fontSize={0.38} color="#2b2622"
            anchorX="center" anchorY="middle">
        {s.id}
      </Text>
    </group>
  );
}

function Warehouse() {
  return (
    <group>
      <mesh position={[0, 1.4, 0]}>
        <boxGeometry args={[4.2, 2.8, 3.2]} />
        <meshStandardMaterial color="#d9641e" />
      </mesh>
      <mesh position={[0, 3, 0]} rotation={[0, Math.PI / 4, 0]}>
        <coneGeometry args={[3.2, 1, 4]} />
        <meshStandardMaterial color="#7a2e2e" />
      </mesh>
      {[-1.2, 0, 1.2].map((x) => (
        <mesh key={x} position={[x, 0.7, 1.62]}>
          <boxGeometry args={[0.9, 1.3, 0.05]} />
          <meshStandardMaterial color="#fbf6ec" />
        </mesh>
      ))}
      <Text position={[0, 4, 0]} fontSize={0.6} color="#2b2622" anchorX="center">WH-KOL</Text>
    </group>
  );
}

function Forklift({ from, to, colour, offset }: { from: string; to: string; colour: string; offset: number }) {
  const g = useRef<THREE.Group>(null);
  const a = pos.get(from)!, b = pos.get(to)!;
  const dir = useMemo(() => b.clone().sub(a), [a, b]);
  const yaw = Math.atan2(dir.x, dir.z);
  useFrame(({ clock }) => {
    if (!g.current) return;
    const t = ((clock.elapsedTime * 0.12 + offset) % 1);
    g.current.position.copy(a.clone().lerp(b, t)).setY(0);
    g.current.rotation.y = yaw;
  });
  return (
    <group ref={g}>
      <mesh position={[0, 0.25, 0]}>
        <boxGeometry args={[0.5, 0.35, 0.8]} />
        <meshStandardMaterial color="#f4c542" />
      </mesh>
      <mesh position={[0, 0.6, 0.15]}>
        <boxGeometry args={[0.45, 0.4, 0.45]} />
        <meshStandardMaterial color={colour} />
      </mesh>
    </group>
  );
}

function RouteLine({ from, to, colour }: { from: string; to: string; colour: string }) {
  const geom = useMemo(() => {
    const pts = [pos.get(from)!.clone().setY(0.02), pos.get(to)!.clone().setY(0.02)];
    return new THREE.BufferGeometry().setFromPoints(pts);
  }, [from, to]);
  return (
    <line>
      <primitive object={geom} attach="geometry" />
      <lineBasicMaterial color={colour} transparent opacity={0.5} />
    </line>
  );
}

export default function Warehouse3D() {
  return (
    <Canvas camera={{ position: [0, 13, 17], fov: 45 }} dpr={[1, 2]}>
      <color attach="background" args={["#fbf6ec"]} />
      <ambientLight intensity={0.7} />
      <directionalLight position={[8, 14, 6]} intensity={1.1} />
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[12.5, 64]} />
        <meshStandardMaterial color="#f3ebdc" />
      </mesh>
      <Warehouse />
      {STORES.map((s) => <StoreRack key={s.id} s={s} />)}
      {ROUTES.map(([f, t, c], i) => (
        <group key={i}>
          <RouteLine from={f} to={t} colour={c} />
          <Forklift from={f} to={t} colour={c} offset={i / ROUTES.length} />
          <Forklift from={f} to={t} colour={c} offset={i / ROUTES.length + 0.5} />
        </group>
      ))}
      <ContactShadows position={[0, 0.01, 0]} opacity={0.35} scale={26} blur={2.5} far={6} />
      <OrbitControls autoRotate autoRotateSpeed={0.6} enablePan={false} minDistance={10} maxDistance={30}
                     maxPolarAngle={Math.PI / 2.2} />
    </Canvas>
  );
}
