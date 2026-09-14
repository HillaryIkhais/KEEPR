/* ── Landing: Three.js hero, story engine, scroll reveals, live stats ── */
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

/* ── Scroll reveal ── */
const revealObs = new IntersectionObserver(es => {
  es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); revealObs.unobserve(e.target); } });
}, { threshold: .12 });
$$('.reveal').forEach(el => revealObs.observe(el));

/* ── Live stats ── */
async function loadStats() {
  try {
    const r = await fetch('/api/worker/status');
    if (!r.ok) return;
    const d = await r.json();
    const c = d.counts || {};
    const total = 50, comp = (c.completed||0)+(c.recovered||0);
    const rate = total > 0 ? Math.round(((total-(c.escalated||0))/total)*100) : 0;
    $('#ps-total').textContent = total;
    $('#ps-rate').textContent = rate + '%';
    $('#ps-recovered').textContent = c.recovered || 0;
    $('#ps-escalated').textContent = c.escalated || 0;
  } catch(e) {}
}
loadStats();

/* ── Three.js hero ── */
let THREE, scene, camera, renderer, core, boundary, invoices = [], particles;
let pointer = { x: 0, y: 0 };
let currentStory = 'normal';
const prefersReduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

function initHero() {
  const wrap = $('#hero-scene');
  const canvas = document.createElement('canvas');
  wrap.insertBefore(canvas, wrap.firstChild);
  const w = wrap.clientWidth, h = wrap.clientHeight;

  THREE = window.THREE;
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(42, w / h, .1, 100);
  camera.position.set(0, 2.4, 9.5);
  camera.lookAt(0, 0, 0);

  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);

  scene.add(new THREE.AmbientLight(0xffffff, .95));
  const dl = new THREE.DirectionalLight(0xffffff, .6);
  dl.position.set(3, 5, 6); scene.add(dl);

  /* Core — sharp dodecahedron, smooth shading */
  core = new THREE.Group();
  const coreMat = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xff4d00, emissiveIntensity: .15, roughness: .3, metalness: .1 });
  const coreMesh = new THREE.Mesh(new THREE.DodecahedronGeometry(1.1, 0), coreMat);
  core.add(coreMesh);
  const wireMat = new THREE.LineBasicMaterial({ color: 0xff4d00, transparent: true, opacity: .25 });
  const wireGeo = new THREE.WireframeGeometry(new THREE.DodecahedronGeometry(1.5, 0));
  core.add(new THREE.LineSegments(wireGeo, wireMat));
  scene.add(core);

  /* Boundary ring */
  const bGeo = new THREE.TorusGeometry(3.1, .015, 8, 80);
  const bMat = new THREE.MeshBasicMaterial({ color: 0xff4d00, transparent: true, opacity: .3 });
  boundary = new THREE.Mesh(bGeo, bMat);
  boundary.rotation.x = Math.PI / 2;
  scene.add(boundary);

  /* Invoices — larger, no flatShading */
  const invoiceMat = new THREE.MeshStandardMaterial({ color: 0x9a978e, roughness: .5, metalness: .05 });
  const geo = new THREE.BoxGeometry(.32, .32, .32);
  for (let i = 0; i < 16; i++) {
    const a = (i / 16) * Math.PI * 2;
    const mesh = new THREE.Mesh(geo, invoiceMat.clone());
    mesh.position.set(Math.cos(a) * 4.3, 0, Math.sin(a) * 4.3);
    mesh.userData = { baseAngle: a, state: 'pending', target: null, path: [], pathT: 0 };
    scene.add(mesh);
    invoices.push(mesh);
  }

  /* Particles — fewer, subtle drift */
  const pCount = 32;
  const pGeo = new THREE.BufferGeometry();
  const pPos = new Float32Array(pCount * 3);
  for (let i = 0; i < pCount; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const r = 5 + Math.random() * 3;
    pPos[i*3] = r * Math.sin(phi) * Math.cos(theta);
    pPos[i*3+1] = r * Math.sin(phi) * Math.sin(theta);
    pPos[i*3+2] = r * Math.cos(phi);
  }
  pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
  particles = new THREE.Points(pGeo, new THREE.PointsMaterial({ color: 0xb0ad9f, size: .035, transparent: true, opacity: .4 }));
  scene.add(particles);

  /* Pointer parallax */
  document.addEventListener('mousemove', e => {
    pointer.x = (e.clientX / innerWidth) * 2 - 1;
    pointer.y = (e.clientY / innerHeight) * 2 - 1;
  });

  /* Resize */
  window.addEventListener('resize', () => {
    const w2 = wrap.clientWidth, h2 = wrap.clientHeight;
    camera.aspect = w2 / h2;
    camera.updateProjectionMatrix();
    renderer.setSize(w2, h2);
  });

  animate();
}

function easeInOut(t) {
  return t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

function animate() {
  requestAnimationFrame(animate);
  const t = performance.now() * .001;
  if (!prefersReduced) {
    core.rotation.y = t * .12;
    core.rotation.x = Math.sin(t * .25) * .06;
    boundary.rotation.z = t * .03;
    particles.rotation.y = t * .015;
    camera.position.x = pointer.x * .25;
    camera.position.y = 2.4 + pointer.y * -.12;
    camera.lookAt(0, 0, 0);
  }

  /* Invoice orbits + path interpolation with easing */
  for (const inv of invoices) {
    const ud = inv.userData;
    if (ud.path.length > 0) {
      ud.pathT += .006;
      if (ud.pathT >= 1) {
        ud.pathT = 0;
        const pt = ud.path.shift();
        inv.position.copy(pt);
        if (ud.path.length === 0) {
          const mat = { verified: 0x0e8a3e, frozen: 0x7b2fd6, escalated: 0xd99e00 }[ud.state] || 0x9a978e;
          inv.material = new THREE.MeshStandardMaterial({ color: mat, roughness: .5, metalness: .05 });
        }
      }
      if (ud.path.length > 0) {
        const from = ud.path.length === 1 ? inv.position : ud.path[0];
        const to = ud.path[0];
        inv.position.lerpVectors(from, to, easeInOut(ud.pathT));
      }
    } else if (!prefersReduced) {
      const a = ud.baseAngle + t * .1;
      inv.position.x = Math.cos(a) * 4.3;
      inv.position.z = Math.sin(a) * 4.3;
      inv.rotation.y = t * .04;
    }
  }

  renderer.render(scene, camera);
}

/* ── Story engine ── */
const stories = {
  normal: {
    title: 'Invoice → Worker → Action → Verify → Resolved',
    desc: 'Normal autonomous flow. Every invoice verified against authoritative ledger state.',
    run: (n) => {
      resetInvoices();
      const inv = invoices[n % invoices.length];
      const pts = [
        inv.position.clone(),
        new THREE.Vector3(-2.2, 0, 0),
        new THREE.Vector3(-.5, 0, 0),
        new THREE.Vector3(.5, 0, 0),
        new THREE.Vector3(2.2, 0, 0),
        new THREE.Vector3(4.3, 0, 0)
      ];
      inv.userData.path = pts.slice(1);
      inv.userData.pathT = 0;
      inv.userData.state = 'verified';
      inv.material = new THREE.MeshStandardMaterial({ color: 0xff4d00, roughness: .4, metalness: .1 });
      pulseCore(0xff4d00);
    }
  },
  failure: {
    title: 'Worker → Failure → KEEPR Recovers → Verify → Resolved',
    desc: 'Operation fails. KEEPR classifies, recovers, verifies against authoritative state, then resumes.',
    run: (n) => {
      resetInvoices();
      const inv = invoices[n % invoices.length];
      const pts = [
        new THREE.Vector3(-2.2, 0, 0),
        new THREE.Vector3(-.5, 0, 0),
        new THREE.Vector3(0, 0, 0),
        new THREE.Vector3(-1.2, 0, 0),
        new THREE.Vector3(0, 0, 0),
        new THREE.Vector3(2.2, 0, 0),
        new THREE.Vector3(4.3, 0, 0)
      ];
      inv.userData.path = pts;
      inv.userData.pathT = 0;
      inv.userData.state = 'verified';
      setTimeout(() => pulseCore(0xe03e4a), 1200);
      setTimeout(() => pulseCore(0x0e8a3e), 3200);
    }
  },
  unsafe: {
    title: 'Worker Requests Out-of-Scope Access → KEEPR Blocks',
    desc: 'Authority widening attempt intercepted before any adapter is touched. Adapter never executed.',
    run: (n) => {
      resetInvoices();
      const inv = invoices[n % invoices.length];
      inv.material = new THREE.MeshStandardMaterial({ color: 0xe03e4a, roughness: .5, metalness: .05 });
      inv.position.set(-2.2, 0, 0);
      const pts = [new THREE.Vector3(-3.2, 0, 0), new THREE.Vector3(-3.15, 0, 0)];
      inv.userData.path = pts;
      inv.userData.pathT = 0;
      inv.userData.state = 'escalated';
      setTimeout(() => {
        boundary.material = new THREE.MeshBasicMaterial({ color: 0xe03e4a, transparent: true, opacity: .7 });
        pulseCore(0xe03e4a);
        setTimeout(() => { boundary.material = new THREE.MeshBasicMaterial({ color: 0xff4d00, transparent: true, opacity: .3 }); }, 800);
      }, 1000);
    }
  },
  false: {
    title: 'Agent Claims Complete → Ledger Disagrees → KEEPR Rejects → Frozen',
    desc: 'Agent says COMPLETED. Authoritative ledger says REFUNDED. Claim rejected. Rollback. Item frozen.',
    run: (n) => {
      resetInvoices();
      const inv = invoices[n % invoices.length];
      inv.position.set(4.3, 0, 0);
      inv.material = new THREE.MeshStandardMaterial({ color: 0x0e8a3e, roughness: .5, metalness: .05 });
      setTimeout(() => {
        inv.material = new THREE.MeshStandardMaterial({ color: 0xe03e4a, roughness: .5, metalness: .05 });
        pulseCore(0xe03e4a);
      }, 800);
      setTimeout(() => {
        inv.material = new THREE.MeshStandardMaterial({ color: 0x7b2fd6, roughness: .5, metalness: .05 });
        inv.userData.state = 'frozen';
      }, 1800);
    }
  }
};

function resetInvoices() {
  for (const inv of invoices) {
    inv.userData.path = [];
    inv.userData.pathT = 0;
    inv.userData.state = 'pending';
    const a = inv.userData.baseAngle;
    inv.position.set(Math.cos(a) * 4.3, 0, Math.sin(a) * 4.3);
    inv.material = new THREE.MeshStandardMaterial({ color: 0x9a978e, roughness: .5, metalness: .05 });
  }
}

function pulseCore(color) {
  if (!core) return;
  core.children[0].material.emissive.setHex(color);
  core.children[0].material.emissiveIntensity = .5;
  setTimeout(() => {
    core.children[0].material.emissive.setHex(0xff4d00);
    core.children[0].material.emissiveIntensity = .15;
  }, 500);
}

let storyIdx = 0, storyTimer, storyCounter = 0;
function playStory(name) {
  currentStory = name;
  const s = stories[name];
  $('#story-title').textContent = s.title;
  $('#story-desc').textContent = s.desc;
  $$('.story-btn').forEach(b => b.classList.toggle('active', b.dataset.story === name));
  s.run(storyCounter++);
  clearTimeout(storyTimer);
  storyTimer = setTimeout(() => {
    const keys = Object.keys(stories);
    storyIdx = (keys.indexOf(name) + 1) % keys.length;
    playStory(keys[storyIdx]);
  }, 6000);
}

$$('.story-btn').forEach(b => b.addEventListener('click', () => playStory(b.dataset.story)));

/* ── Init ── */
(async () => {
  try {
    const mod = await import('https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js');
    window.THREE = mod;
    initHero();
    setTimeout(() => playStory('normal'), 800);
  } catch (e) {
    $('#hero-fallback').style.display = 'flex';
    const canvas = $('#hero-scene canvas');
    if (canvas) canvas.remove();
  }
})();
