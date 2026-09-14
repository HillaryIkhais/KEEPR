/* ── Landing: Living network hero, story engine, scroll reveals, live stats ── */
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
    const total = 50;
    const rate = total > 0 ? Math.round(((total-(c.escalated||0))/total)*100) : 0;
    $('#ps-total').textContent = total;
    $('#ps-rate').textContent = rate + '%';
    $('#ps-recovered').textContent = c.recovered || 0;
    $('#ps-escalated').textContent = c.escalated || 0;
  } catch(e) {}
}
loadStats();

/* ── Three.js living network hero ── */
let THREE, scene, camera, renderer, nodes = [], lines = [], boundary;
let pointer = { x: 0, y: 0 };
const prefersReduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

const NODE_COUNT = 24;
const NODE_SPREAD = 4.5;
const CONNECT_DIST = 3.2;

function initHero() {
  const wrap = $('#hero-scene');
  const canvas = document.createElement('canvas');
  wrap.insertBefore(canvas, wrap.firstChild);
  const w = wrap.clientWidth, h = wrap.clientHeight;

  THREE = window.THREE;
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(38, w / h, .1, 100);
  camera.position.set(0, 1.8, 9);
  camera.lookAt(0, 0, 0);

  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);

  scene.add(new THREE.AmbientLight(0xffffff, .9));
  const dl = new THREE.DirectionalLight(0xffffff, .5);
  dl.position.set(4, 6, 5); scene.add(dl);

  /* Create network nodes */
  const nodeGeo = new THREE.IcosahedronGeometry(.12, 0);
  const nodeMat = new THREE.MeshStandardMaterial({ color: 0xc0bdb4, roughness: .4, metalness: .1 });
  const activeMat = new THREE.MeshStandardMaterial({ color: 0xff4d00, emissive: 0xff4d00, emissiveIntensity: .3, roughness: .3 });
  const failMat = new THREE.MeshStandardMaterial({ color: 0xe03e4a, emissive: 0xe03e4a, emissiveIntensity: .4, roughness: .3 });
  const verifiedMat = new THREE.MeshStandardMaterial({ color: 0x0e8a3e, emissive: 0x0e8a3e, emissiveIntensity: .25, roughness: .3 });
  const frozenMat = new THREE.MeshStandardMaterial({ color: 0x7b2fd6, emissive: 0x7b2fd6, emissiveIntensity: .3, roughness: .3 });

  for (let i = 0; i < NODE_COUNT; i++) {
    const mesh = new THREE.Mesh(nodeGeo, nodeMat.clone());
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const r = NODE_SPREAD * (.4 + Math.random() * .6);
    mesh.position.set(
      r * Math.sin(phi) * Math.cos(theta),
      r * Math.sin(phi) * Math.sin(theta) * .6,
      r * Math.cos(phi) * .8
    );
    mesh.userData = {
      base: mesh.position.clone(),
      phase: Math.random() * Math.PI * 2,
      speed: .3 + Math.random() * .4,
      state: 'idle',
      pulseT: 0
    };
    scene.add(mesh);
    nodes.push(mesh);
  }

  /* Create connection lines between nearby nodes */
  const lineMat = new THREE.LineBasicMaterial({ color: 0xb0ad9f, transparent: true, opacity: .12 });
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const d = nodes[i].position.distanceTo(nodes[j].position);
      if (d < CONNECT_DIST) {
        const geo = new THREE.BufferGeometry().setFromPoints([nodes[i].position, nodes[j].position]);
        const line = new THREE.Line(geo, lineMat.clone());
        line.userData = { a: i, b: j, baseOpacity: .12 };
        scene.add(line);
        lines.push(line);
      }
    }
  }

  /* Boundary ring */
  const bGeo = new THREE.TorusGeometry(3.4, .012, 8, 80);
  const bMat = new THREE.MeshBasicMaterial({ color: 0xff4d00, transparent: true, opacity: .2 });
  boundary = new THREE.Mesh(bGeo, bMat);
  boundary.rotation.x = Math.PI / 2;
  scene.add(boundary);

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

function animate() {
  requestAnimationFrame(animate);
  const t = performance.now() * .001;

  if (!prefersReduced) {
    /* Breathe nodes — organic floating motion */
    for (const n of nodes) {
      const ud = n.userData;
      n.position.x = ud.base.x + Math.sin(t * ud.speed + ud.phase) * .15;
      n.position.y = ud.base.y + Math.cos(t * ud.speed * .7 + ud.phase) * .1;
      n.position.z = ud.base.z + Math.sin(t * ud.speed * .5 + ud.phase * 2) * .08;

      /* Pulse active nodes */
      if (ud.pulseT > 0) {
        ud.pulseT -= .02;
        const s = 1 + Math.sin((1 - ud.pulseT) * Math.PI) * .15;
        n.scale.set(s, s, s);
      } else {
        n.scale.set(1, 1, 1);
      }
    }

    /* Update connection lines */
    for (const line of lines) {
      const a = nodes[line.userData.a];
      const b = nodes[line.userData.b];
      const pos = line.geometry.attributes.position;
      pos.setXYZ(0, a.position.x, a.position.y, a.position.z);
      pos.setXYZ(1, b.position.x, b.position.y, b.position.z);
      pos.needsUpdate = true;

      /* Lines glow when connected nodes are active */
      const aActive = a.userData.state !== 'idle';
      const bActive = b.userData.state !== 'idle';
      line.material.opacity = aActive || bActive ? .35 : line.userData.baseOpacity;
      if (aActive || bActive) {
        line.material.color.setHex(0xff4d00);
      } else {
        line.material.color.setHex(0xb0ad9f);
      }
    }

    /* Boundary slow rotation */
    boundary.rotation.z = t * .02;

    /* Camera parallax */
    camera.position.x = pointer.x * .2;
    camera.position.y = 1.8 + pointer.y * -.1;
    camera.lookAt(0, 0, 0);
  }

  renderer.render(scene, camera);
}

/* ── Story engine ── */
const stories = {
  normal: {
    title: 'Invoice / Worker / Action / Verify / Resolved',
    desc: 'Normal autonomous flow. Every invoice verified against authoritative ledger state.',
    run: () => {
      resetNetwork();
      /* Light up a path through the network */
      const path = [0, 3, 7, 11, 15, 18];
      path.forEach((idx, i) => {
        setTimeout(() => {
          if (nodes[idx]) {
            nodes[idx].userData.state = 'active';
            nodes[idx].material = nodes[idx].material.clone();
            nodes[idx].material.emissive.setHex(0xff4d00);
            nodes[idx].material.emissiveIntensity = .3;
            nodes[idx].userData.pulseT = 1;
          }
          if (i === path.length - 1) {
            setTimeout(() => {
              path.forEach(j => {
                if (nodes[j]) {
                  nodes[j].userData.state = 'verified';
                  nodes[j].material.emissive.setHex(0x0e8a3e);
                  nodes[j].material.emissiveIntensity = .25;
                }
              });
            }, 400);
          }
        }, i * 350);
      });
    }
  },
  failure: {
    title: 'Worker / Failure / KEEPR Recovers / Verify / Resolved',
    desc: 'Operation fails. KEEPR classifies, recovers, verifies against authoritative state, then resumes.',
    run: () => {
      resetNetwork();
      const failNode = 9;
      /* Normal flow first */
      [0, 3, 7].forEach((idx, i) => {
        setTimeout(() => {
          if (nodes[idx]) {
            nodes[idx].userData.state = 'active';
            nodes[idx].material.emissive.setHex(0xff4d00);
            nodes[idx].material.emissiveIntensity = .3;
            nodes[idx].userData.pulseT = 1;
          }
        }, i * 300);
      });
      /* Failure */
      setTimeout(() => {
        if (nodes[failNode]) {
          nodes[failNode].userData.state = 'fail';
          nodes[failNode].material.emissive.setHex(0xe03e4a);
          nodes[failNode].material.emissiveIntensity = .5;
          nodes[failNode].userData.pulseT = 1;
          pulseBoundary(0xe03e4a);
        }
      }, 1100);
      /* Recovery */
      setTimeout(() => {
        if (nodes[failNode]) {
          nodes[failNode].userData.state = 'active';
          nodes[failNode].material.emissive.setHex(0xff4d00);
          nodes[failNode].material.emissiveIntensity = .3;
          nodes[failNode].userData.pulseT = 1;
        }
      }, 2200);
      /* Verified */
      setTimeout(() => {
        [0, 3, 7, failNode].forEach(j => {
          if (nodes[j]) {
            nodes[j].userData.state = 'verified';
            nodes[j].material.emissive.setHex(0x0e8a3e);
            nodes[j].material.emissiveIntensity = .25;
          }
        });
      }, 3000);
    }
  },
  unsafe: {
    title: 'Worker Requests Out-of-Scope Access / KEEPR Blocks',
    desc: 'Authority widening attempt intercepted before any adapter is touched.',
    run: () => {
      resetNetwork();
      const blockNode = 12;
      [0, 4].forEach((idx, i) => {
        setTimeout(() => {
          if (nodes[idx]) {
            nodes[idx].userData.state = 'active';
            nodes[idx].material.emissive.setHex(0xff4d00);
            nodes[idx].material.emissiveIntensity = .3;
            nodes[idx].userData.pulseT = 1;
          }
        }, i * 300);
      });
      /* Blocked — hits boundary */
      setTimeout(() => {
        if (nodes[blockNode]) {
          nodes[blockNode].userData.state = 'fail';
          nodes[blockNode].material.emissive.setHex(0xe03e4a);
          nodes[blockNode].material.emissiveIntensity = .5;
          nodes[blockNode].userData.pulseT = 1;
          pulseBoundary(0xe03e4a);
        }
      }, 800);
      /* Others continue */
      setTimeout(() => {
        [0, 4, 1, 5].forEach(j => {
          if (nodes[j]) {
            nodes[j].userData.state = 'verified';
            nodes[j].material.emissive.setHex(0x0e8a3e);
            nodes[j].material.emissiveIntensity = .25;
          }
        });
      }, 2000);
    }
  },
  false: {
    title: 'Agent Claims Complete / Ledger Disagrees / KEEPR Rejects / Frozen',
    desc: 'Agent says COMPLETED. Authoritative ledger says REFUNDED. Claim rejected. Rollback. Frozen.',
    run: () => {
      resetNetwork();
      const frozenNode = 16;
      /* Agent claims done */
      setTimeout(() => {
        if (nodes[frozenNode]) {
          nodes[frozenNode].userData.state = 'active';
          nodes[frozenNode].material.emissive.setHex(0x0e8a3e);
          nodes[frozenNode].material.emissiveIntensity = .3;
          nodes[frozenNode].userData.pulseT = 1;
        }
      }, 300);
      /* Rejection */
      setTimeout(() => {
        if (nodes[frozenNode]) {
          nodes[frozenNode].userData.state = 'fail';
          nodes[frozenNode].material.emissive.setHex(0xe03e4a);
          nodes[frozenNode].material.emissiveIntensity = .5;
          nodes[frozenNode].userData.pulseT = 1;
          pulseBoundary(0xe03e4a);
        }
      }, 1000);
      /* Frozen */
      setTimeout(() => {
        if (nodes[frozenNode]) {
          nodes[frozenNode].userData.state = 'frozen';
          nodes[frozenNode].material.emissive.setHex(0x7b2fd6);
          nodes[frozenNode].material.emissiveIntensity = .35;
          nodes[frozenNode].userData.pulseT = 1;
        }
      }, 1800);
      /* Others verified */
      setTimeout(() => {
        [0, 3, 7, 11].forEach(j => {
          if (nodes[j]) {
            nodes[j].userData.state = 'verified';
            nodes[j].material.emissive.setHex(0x0e8a3e);
            nodes[j].material.emissiveIntensity = .25;
          }
        });
      }, 2400);
    }
  }
};

function resetNetwork() {
  for (const n of nodes) {
    n.userData.state = 'idle';
    n.userData.pulseT = 0;
    n.material.emissive.setHex(0x000000);
    n.material.emissiveIntensity = 0;
    n.material.color.setHex(0xc0bdb4);
    n.scale.set(1, 1, 1);
  }
  for (const line of lines) {
    line.material.opacity = line.userData.baseOpacity;
    line.material.color.setHex(0xb0ad9f);
  }
}

function pulseBoundary(color) {
  if (!boundary) return;
  boundary.material.color.setHex(color);
  boundary.material.opacity = .6;
  setTimeout(() => {
    boundary.material.color.setHex(0xff4d00);
    boundary.material.opacity = .2;
  }, 600);
}

let storyIdx = 0, storyTimer;
function playStory(name) {
  const s = stories[name];
  $('#story-title').textContent = s.title;
  $('#story-desc').textContent = s.desc;
  $$('.story-btn').forEach(b => b.classList.toggle('active', b.dataset.story === name));
  s.run();
  clearTimeout(storyTimer);
  storyTimer = setTimeout(() => {
    const keys = Object.keys(stories);
    storyIdx = (keys.indexOf(name) + 1) % keys.length;
    playStory(keys[storyIdx]);
  }, 5500);
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
