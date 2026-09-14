"""Dashboard HTML — ChainGPT Labs-inspired alive UI for KEEPR.

White/light aesthetic, 3D elements, particle effects, animated grid,
bold mirrored typography, orange accent. The dashboard breathes.
"""
from __future__ import annotations

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>KEEPR — Autonomous Recovery</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#f5f5f0;--bg2:#eaeae5;--fg:#0a0a0a;--fg2:#3a3a3a;--fg3:#888;
  --accent:#FF5722;--accent2:#FF8A65;--accent-glow:rgba(255,87,34,.15);
  --green:#00C853;--red:#FF1744;--yellow:#FFD600;--purple:#AA00FF;
  --card:#fff;--card-border:#e0e0d8;--grid-line:rgba(0,0,0,.04);
  --radius:12px;--shadow:0 2px 20px rgba(0,0,0,.06);
}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--fg);font-family:'Space Grotesk',sans-serif;
     overflow-x:hidden;position:relative;min-height:100vh}

/* ── Animated Grid Background ── */
.grid-bg{position:fixed;inset:0;z-index:0;pointer-events:none;
         background-image:
           linear-gradient(var(--grid-line) 1px,transparent 1px),
           linear-gradient(90deg,var(--grid-line) 1px,transparent 1px);
         background-size:60px 60px;
         animation:gridShift 20s linear infinite}
@keyframes gridShift{0%{background-position:0 0}100%{background-position:60px 60px}}

/* ── Particles ── */
.particles{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden}
.particle{position:absolute;width:3px;height:3px;background:var(--accent);
          border-radius:50%;opacity:0;animation:particleFloat linear infinite}
@keyframes particleFloat{
  0%{opacity:0;transform:translateY(100vh) scale(0)}
  10%{opacity:.6}
  90%{opacity:.6}
  100%{opacity:0;transform:translateY(-10vh) scale(1)}
}

/* ── Navigation ── */
nav{position:sticky;top:0;z-index:100;display:flex;align-items:center;
    justify-content:space-between;padding:1rem 2.5rem;
    background:rgba(245,245,240,.85);backdrop-filter:blur(20px);
    border-bottom:1px solid var(--card-border)}
nav .logo{display:flex;align-items:center;gap:.75rem;text-decoration:none}
nav .logo-icon{width:36px;height:36px;background:var(--accent);border-radius:8px;
               display:flex;align-items:center;justify-content:center;
               font-weight:700;color:#fff;font-size:.85rem;
               box-shadow:0 2px 12px rgba(255,87,34,.3);
               transition:transform .3s,box-shadow .3s}
nav .logo:hover .logo-icon{transform:rotate(-8deg) scale(1.08);
                            box-shadow:0 4px 20px rgba(255,87,34,.4)}
nav .logo-text{font-weight:700;font-size:1.1rem;letter-spacing:.08em;color:var(--fg)}
nav .logo-sub{font-size:.6rem;text-transform:uppercase;letter-spacing:.15em;
              color:var(--fg3);margin-top:-2px}
nav .nav-links{display:flex;gap:2rem;align-items:center}
nav .nav-links a{font-size:.75rem;text-transform:uppercase;letter-spacing:.1em;
                 color:var(--fg2);text-decoration:none;font-weight:500;
                 transition:color .2s;position:relative}
nav .nav-links a::after{content:'';position:absolute;bottom:-4px;left:0;
                        width:0;height:2px;background:var(--accent);
                        transition:width .3s cubic-bezier(.4,0,.2,1)}
nav .nav-links a:hover{color:var(--accent)}
nav .nav-links a:hover::after{width:100%}
nav .status-dot{width:8px;height:8px;border-radius:50%;background:var(--green);
                animation:pulse 2s ease-in-out infinite;cursor:pointer;
                position:relative}
nav .status-dot::after{content:'';position:absolute;inset:-4px;border-radius:50%;
                       border:2px solid var(--green);opacity:.3;
                       animation:pulseRing 2s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.6;transform:scale(.85)}}
@keyframes pulseRing{0%,100%{opacity:.3;transform:scale(1)}50%{opacity:0;transform:scale(1.6)}}

/* ── Hero Section ── */
.hero{position:relative;z-index:1;display:grid;grid-template-columns:1fr 1fr;
      gap:2rem;padding:4rem 2.5rem 3rem;min-height:50vh;align-items:center}
.hero-left{position:relative}
.hero-title{font-size:clamp(3rem,8vw,6.5rem);font-weight:700;line-height:.9;
            letter-spacing:-.03em;color:var(--fg);position:relative}
.hero-title .mirror{display:block;font-size:clamp(2.5rem,7vw,5.5rem);
                    color:transparent;-webkit-text-stroke:2px var(--fg);
                    transform:scaleY(-1);opacity:.12;margin-top:-.3em;
                    filter:blur(1px);user-select:none}
.hero-title .accent{color:var(--accent);position:relative;display:inline-block}
.hero-title .accent::after{content:'';position:absolute;bottom:0;left:0;
                           width:100%;height:4px;background:var(--accent);
                           border-radius:2px;transform:scaleX(0);
                           transform-origin:left;transition:transform .6s cubic-bezier(.4,0,.2,1)}
.hero-title:hover .accent::after{transform:scaleX(1)}
.hero-sub{font-size:1rem;color:var(--fg2);margin-top:1.5rem;max-width:400px;
          line-height:1.7;font-weight:400}
.hero-sub strong{color:var(--accent);font-weight:600}
.hero-cta{display:flex;gap:1rem;margin-top:2rem}
.btn{padding:.85rem 2rem;border-radius:8px;font-family:inherit;font-weight:600;
     font-size:.8rem;letter-spacing:.05em;text-transform:uppercase;cursor:pointer;
     transition:all .3s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden;
     border:none;text-decoration:none}
.btn-primary{background:var(--accent);color:#fff;
             box-shadow:0 4px 24px rgba(255,87,34,.3)}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 32px rgba(255,87,34,.45)}
.btn-primary:active{transform:translateY(0)}
.btn-primary::before{content:'';position:absolute;inset:0;
                     background:linear-gradient(135deg,rgba(255,255,255,.2),transparent);
                     opacity:0;transition:opacity .3s}
.btn-primary:hover::before{opacity:1}
.btn-outline{background:transparent;color:var(--fg);border:2px solid var(--card-border)}
.btn-outline:hover{border-color:var(--fg);transform:translateY(-2px)}

/* ── 3D Hero Element ── */
.hero-right{display:flex;align-items:center;justify-content:center;perspective:800px}
.shield-3d{width:280px;height:320px;position:relative;transform-style:preserve-3d;
            animation:shieldFloat 6s ease-in-out infinite}
@keyframes shieldFloat{0%,100%{transform:rotateY(-8deg) rotateX(5deg) translateY(0)}
                       50%{transform:rotateY(8deg) rotateX(-3deg) translateY(-15px)}}
.shield-body{position:absolute;inset:0;background:linear-gradient(145deg,#fff,#e8e8e0);
             border-radius:20px;border:1px solid var(--card-border);
             box-shadow:0 20px 60px rgba(0,0,0,.08),0 1px 3px rgba(0,0,0,.04),
                        inset 0 1px 0 rgba(255,255,255,.8);
             display:flex;align-items:center;justify-content:center;
             transform:translateZ(40px)}
.shield-body::before{content:'';position:absolute;inset:8px;border-radius:14px;
                     border:2px dashed rgba(255,87,34,.2)}
.shield-icon{font-size:5rem;filter:drop-shadow(0 4px 12px rgba(0,0,0,.1));
             animation:iconPulse 3s ease-in-out infinite}
@keyframes iconPulse{0%,100%{transform:scale(1)}50%{transform:scale(1.05)}}
.shield-ring{position:absolute;inset:-20px;border-radius:28px;
             border:1px solid rgba(255,87,34,.15);
             animation:ringRotate 15s linear infinite}
.shield-ring::before{content:'';position:absolute;top:-4px;left:50%;
                     width:8px;height:8px;background:var(--accent);border-radius:50%;
                     box-shadow:0 0 12px var(--accent)}
@keyframes ringRotate{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
.shield-shadow{position:absolute;bottom:-30px;left:50%;transform:translateX(-50%);
               width:200px;height:30px;background:radial-gradient(ellipse,rgba(0,0,0,.08),transparent);
               border-radius:50%;animation:shadowPulse 6s ease-in-out infinite}
@keyframes shadowPulse{0%,100%{transform:translateX(-50%) scaleX(1);opacity:.8}
                       50%{transform:translateX(-50%) scaleX(.85);opacity:.5}}

/* ── Stats Grid ── */
.stats-section{position:relative;z-index:1;padding:0 2.5rem 3rem}
.stats-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:1rem}
.stat-card{background:var(--card);border:1px solid var(--card-border);
           border-radius:var(--radius);padding:1.5rem 1.25rem;text-align:center;
           position:relative;overflow:hidden;cursor:default;
           transition:all .4s cubic-bezier(.4,0,.2,1);
           transform-style:preserve-3d;perspective:600px}
.stat-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;
                   background:var(--accent);transform:scaleX(0);
                   transition:transform .4s cubic-bezier(.4,0,.2,1)}
.stat-card:hover{transform:translateY(-6px) rotateX(2deg);
                 box-shadow:0 12px 40px rgba(0,0,0,.08)}
.stat-card:hover::before{transform:scaleX(1)}
.stat-val{font-size:2.2rem;font-weight:700;color:var(--fg);line-height:1;
          font-family:'JetBrains Mono',monospace;transition:color .3s}
.stat-card:hover .stat-val{color:var(--accent)}
.stat-lbl{font-size:.65rem;text-transform:uppercase;letter-spacing:.12em;
          color:var(--fg3);margin-top:.5rem;font-weight:500}
.stat-card .stat-bar{position:absolute;bottom:0;left:0;right:0;height:3px;
                     background:var(--bg2)}
.stat-card .stat-fill{height:100%;background:var(--accent);transition:width .8s cubic-bezier(.4,0,.2,1);
                      border-radius:0 2px 0 0}
.stat-card.accent .stat-val{color:var(--accent)}
.stat-card.green .stat-val{color:var(--green)}
.stat-card.red .stat-val{color:var(--red)}
.stat-card.yellow .stat-val{color:var(--yellow)}
.stat-card.purple .stat-val{color:var(--purple)}

/* ── Section Headers ── */
.section{position:relative;z-index:1;padding:0 2.5rem 2rem}
.section-header{display:flex;align-items:baseline;gap:1rem;margin-bottom:1.5rem}
.section-title{font-size:1.5rem;font-weight:700;letter-spacing:-.02em}
.section-title .mirror{font-size:1.1rem;color:transparent;-webkit-text-stroke:1px var(--fg);
                       transform:scaleY(-1);opacity:.08;display:inline-block;
                       margin-left:.5rem;filter:blur(.5px)}
.section-tag{font-size:.65rem;text-transform:uppercase;letter-spacing:.15em;
             color:var(--fg3);font-weight:500;padding:4px 10px;
             border:1px solid var(--card-border);border-radius:20px}

/* ── Failure Lab ── */
.lab-section{background:var(--card);border:1px solid var(--card-border);
             border-radius:var(--radius);padding:2rem;margin:0 2.5rem 2rem;
             position:relative;z-index:1;overflow:hidden}
.lab-section::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;
                     background:linear-gradient(90deg,transparent,var(--accent),transparent)}
.lab-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:.75rem}
.attack-btn{padding:.9rem 1rem;border-radius:10px;font-family:'JetBrains Mono',monospace;
            font-size:.72rem;font-weight:500;cursor:pointer;
            background:var(--bg);color:var(--fg);border:1px solid var(--card-border);
            transition:all .3s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden;
            text-align:left}
.attack-btn::before{content:'';position:absolute;inset:0;
                    background:linear-gradient(135deg,var(--accent-glow),transparent);
                    opacity:0;transition:opacity .3s}
.attack-btn:hover{border-color:var(--accent);transform:translateY(-3px);
                  box-shadow:0 8px 24px rgba(255,87,34,.12)}
.attack-btn:hover::before{opacity:1}
.attack-btn:active{transform:translateY(-1px) scale(.98)}
.attack-btn .atk-label{font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;
                       color:var(--fg3);display:block;margin-bottom:.3rem}
.attack-btn .atk-code{font-size:.85rem;font-weight:700;color:var(--fg)}
.attack-btn.injected{border-color:var(--green);animation:injectPulse .6s ease}
@keyframes injectPulse{0%{box-shadow:0 0 0 0 rgba(0,200,83,.4)}
                       100%{box-shadow:0 0 0 20px rgba(0,200,83,0)}}
.lab-msg{font-size:.75rem;color:var(--fg3);margin-top:1rem;min-height:1.2rem;
         font-family:'JetBrains Mono',monospace;transition:color .3s}
.lab-msg.active{color:var(--accent)}

/* ── Invoice Table ── */
.table-wrap{background:var(--card);border:1px solid var(--card-border);
            border-radius:var(--radius);overflow:hidden;margin:0 2.5rem 2rem;
            position:relative;z-index:1}
table{width:100%;border-collapse:collapse}
thead{background:var(--bg)}
th{text-align:left;padding:.85rem 1.25rem;font-size:.65rem;text-transform:uppercase;
    letter-spacing:.12em;color:var(--fg3);font-weight:600;
    border-bottom:1px solid var(--card-border)}
td{padding:.7rem 1.25rem;font-size:.8rem;border-bottom:1px solid rgba(0,0,0,.03);
   font-family:'JetBrains Mono',monospace;transition:background .2s}
tr{transition:all .3s}
tr:hover{background:var(--accent-glow)}
tr.selected{background:rgba(255,87,34,.06);box-shadow:inset 3px 0 0 var(--accent)}
.badge{display:inline-flex;align-items:center;gap:5px;padding:4px 10px;
       border-radius:20px;font-size:.65rem;font-weight:600;text-transform:uppercase;
       letter-spacing:.06em}
.badge::before{content:'';width:6px;height:6px;border-radius:50%}
.b-COMPLETED{background:rgba(0,200,83,.1);color:#00862e}
.b-COMPLETED::before{background:#00C853}
.b-RECOVERED{background:rgba(0,200,83,.08);color:#2e7d32}
.b-RECOVERED::before{background:#66BB6A}
.b-ESCALATED{background:rgba(255,214,0,.12);color:#e6a800}
.b-ESCALATED::before{background:#FFD600}
.b-FROZEN{background:rgba(170,0,255,.1);color:#7b1fa2}
.b-FROZEN::before{background:#AA00FF}
.b-PENDING{background:rgba(0,0,0,.04);color:var(--fg3)}
.b-PENDING::before{background:var(--fg3)}
.b-FAILED{background:rgba(255,23,68,.1);color:#c62828}
.b-FAILED::before{background:#FF1744}
.trace-btn{padding:5px 12px;border-radius:6px;font-size:.65rem;font-weight:500;
           background:var(--bg);color:var(--fg2);border:1px solid var(--card-border);
           cursor:pointer;transition:all .2s;font-family:inherit}
.trace-btn:hover{border-color:var(--accent);color:var(--accent)}

/* ── Lifecycle Trace ── */
.lifecycle{background:var(--card);border:1px solid var(--card-border);
           border-radius:var(--radius);padding:1.5rem 2rem;margin:0 2.5rem 3rem;
           position:relative;z-index:1;min-height:80px;overflow:hidden}
.lifecycle::before{content:'';position:absolute;top:0;left:0;bottom:0;width:3px;
                  background:var(--accent);border-radius:0 2px 2px 0}
.lifecycle-label{font-size:.65rem;text-transform:uppercase;letter-spacing:.12em;
                color:var(--fg3);margin-bottom:1rem;font-weight:600}
.lifecycle-steps{display:flex;flex-wrap:wrap;align-items:center;gap:.4rem}
.step{display:inline-flex;align-items:center;padding:5px 12px;border-radius:6px;
      font-size:.7rem;font-family:'JetBrains Mono',monospace;font-weight:500;
      background:var(--bg);border:1px solid var(--card-border);
      opacity:0;transform:translateY(8px);
      animation:stepIn .4s ease forwards}
@keyframes stepIn{to{opacity:1;transform:translateY(0)}}
.step.fail{border-color:rgba(255,23,68,.3);color:#c62828;background:rgba(255,23,68,.04)}
.step.ok{border-color:rgba(0,200,83,.3);color:#2e7d32;background:rgba(0,200,83,.04)}
.step.rec{border-color:rgba(0,200,83,.2);color:#43a047;background:rgba(0,200,83,.03)}
.step.esc{border-color:rgba(255,214,0,.3);color:#e6a800;background:rgba(255,214,0,.05)}
.step.frozen{border-color:rgba(170,0,255,.3);color:#7b1fa2;background:rgba(170,0,255,.04)}
.arrow{color:var(--fg3);font-size:.75rem;opacity:.3}

/* ── Scroll Reveal ── */
.reveal{opacity:0;transform:translateY(30px);transition:all .7s cubic-bezier(.4,0,.2,1)}
.reveal.visible{opacity:1;transform:translateY(0)}

/* ── Footer ── */
footer{position:relative;z-index:1;padding:2rem 2.5rem;border-top:1px solid var(--card-border);
       display:flex;justify-content:space-between;align-items:center}
footer .ft-text{font-size:.7rem;color:var(--fg3);letter-spacing:.05em}
footer .ft-links{display:flex;gap:1.5rem}
footer .ft-links a{font-size:.65rem;color:var(--fg3);text-decoration:none;
                   text-transform:uppercase;letter-spacing:.1em;transition:color .2s}
footer .ft-links a:hover{color:var(--accent)}

/* ── Responsive ── */
@media(max-width:1100px){.stats-grid{grid-template-columns:repeat(3,1fr)}
  .hero{grid-template-columns:1fr}.hero-right{display:none}}
@media(max-width:700px){.stats-grid{grid-template-columns:repeat(2,1fr)}
  nav{padding:1rem}.hero,.stats-section,.section,.lab-section,.table-wrap,.lifecycle{margin-left:1rem;margin-right:1rem;padding-left:1rem;padding-right:1rem}}
</style>
</head>
<body>

<div class="grid-bg"></div>
<div class="particles" id="particles"></div>

<nav>
  <a class="logo" href="/">
    <div class="logo-icon">K</div>
    <div>
      <div class="logo-text">KEEPR</div>
      <div class="logo-sub">Autonomous Recovery</div>
    </div>
  </a>
  <div class="nav-links">
    <a href="#lab">Failure Lab</a>
    <a href="#invoices">Invoices</a>
    <a href="#trace">Lifecycle</a>
    <div class="status-dot" title="System online"></div>
  </div>
</nav>

<section class="hero">
  <div class="hero-left">
    <h1 class="hero-title">
      <span class="accent">KEE</span>PR
      <span class="mirror" aria-hidden="true">KEEPR</span>
    </h1>
    <p class="hero-sub">
      <strong>Recover the work safely.</strong><br>
      Autonomous workers that resolve exceptions before they reach you.
      One failure shouldn't hand the whole job back to a human.
    </p>
    <div class="hero-cta">
      <button class="btn btn-primary" onclick="runWorker()">Run 50 Invoices</button>
      <button class="btn btn-outline" onclick="resetWorker()">Reset</button>
    </div>
  </div>
  <div class="hero-right">
    <div class="shield-3d">
      <div class="shield-ring"></div>
      <div class="shield-body">
        <div class="shield-icon">🛡️</div>
      </div>
      <div class="shield-shadow"></div>
    </div>
  </div>
</section>

<section class="stats-section reveal">
  <div class="stats-grid">
    <div class="stat-card" id="c-pending">
      <div class="stat-val" id="v-pending">50</div>
      <div class="stat-lbl">Remaining</div>
      <div class="stat-bar"><div class="stat-fill" id="bar-pending" style="width:100%"></div></div>
    </div>
    <div class="stat-card green" id="c-completed">
      <div class="stat-val" id="v-completed">0</div>
      <div class="stat-lbl">Completed</div>
      <div class="stat-bar"><div class="stat-fill" id="bar-completed" style="width:0%"></div></div>
    </div>
    <div class="stat-card accent" id="c-recovered">
      <div class="stat-val" id="v-recovered">0</div>
      <div class="stat-lbl">Recovered</div>
      <div class="stat-bar"><div class="stat-fill" id="bar-recovered" style="width:0%"></div></div>
    </div>
    <div class="stat-card yellow" id="c-escalated">
      <div class="stat-val" id="v-escalated">0</div>
      <div class="stat-lbl">Escalated</div>
      <div class="stat-bar"><div class="stat-fill" id="bar-escalated" style="width:0%"></div></div>
    </div>
    <div class="stat-card purple" id="c-frozen">
      <div class="stat-val" id="v-frozen">0</div>
      <div class="stat-lbl">Frozen</div>
      <div class="stat-bar"><div class="stat-fill" id="bar-frozen" style="width:0%"></div></div>
    </div>
    <div class="stat-card accent" id="c-rate">
      <div class="stat-val" id="v-rate">0%</div>
      <div class="stat-lbl">No-Human Rate</div>
      <div class="stat-bar"><div class="stat-fill" id="bar-rate" style="width:0%"></div></div>
    </div>
  </div>
</section>

<section class="section reveal" id="lab">
  <div class="section-header">
    <h2 class="section-title">Failure Lab <span class="mirror" aria-hidden="true">FAILURE LAB</span></h2>
    <span class="section-tag">One click breaks it — KEEPR recovers it</span>
  </div>
</section>
<div class="lab-section reveal">
  <div class="lab-grid">
    <button class="attack-btn" onclick="inject(this,'inv_007','http_503')">
      <span class="atk-label">Transient</span><span class="atk-code">503</span>
    </button>
    <button class="attack-btn" onclick="inject(this,'inv_007','http_401')">
      <span class="atk-label">Auth</span><span class="atk-code">401</span>
    </button>
    <button class="attack-btn" onclick="inject(this,'inv_007','malformed_amount')">
      <span class="atk-label">Poisoned</span><span class="atk-code">MALFORMED</span>
    </button>
    <button class="attack-btn" onclick="inject(this,'inv_007','stale')">
      <span class="atk-label">Stale</span><span class="atk-code">STALE</span>
    </button>
    <button class="attack-btn" onclick="inject(this,'inv_007','conflict')">
      <span class="atk-label">Conflict</span><span class="atk-code">CONFLICT</span>
    </button>
    <button class="attack-btn" onclick="inject(this,'inv_007','partial')">
      <span class="atk-label">Partial</span><span class="atk-code">PARTIAL</span>
    </button>
    <button class="attack-btn" onclick="inject(this,'inv_007','inflated')">
      <span class="atk-label">Inflated</span><span class="atk-code">INFLATED</span>
    </button>
    <button class="attack-btn" onclick="authorityAttack(this)">
      <span class="atk-label">Security</span><span class="atk-code">AUTH WIDEN</span>
    </button>
    <button class="attack-btn" onclick="falseCompletion(this)">
      <span class="atk-label">Deception</span><span class="atk-code">FALSE DONE</span>
    </button>
    <button class="attack-btn" onclick="oscillation(this)">
      <span class="atk-label">Chaos</span><span class="atk-code">OSCILLATE</span>
    </button>
  </div>
  <div class="lab-msg" id="lab-msg"></div>
</div>

<section class="section reveal" id="invoices">
  <div class="section-header">
    <h2 class="section-title">Invoices <span class="mirror" aria-hidden="true">INVOICES</span></h2>
    <span class="section-tag" id="invoice-count">50 records</span>
  </div>
</section>
<div class="table-wrap reveal">
  <table>
    <thead><tr><th>ID</th><th>Status</th><th>Attempts</th><th>Recovery</th><th></th></tr></thead>
    <tbody id="inv-body"></tbody>
  </table>
</div>

<section class="section reveal" id="trace">
  <div class="section-header">
    <h2 class="section-title">Lifecycle Trace <span class="mirror" aria-hidden="true">TRACE</span></h2>
  </div>
</section>
<div class="lifecycle reveal" id="lifecycle-pane">
  <div class="lifecycle-label">Select an invoice to view its recovery journey</div>
  <div class="lifecycle-steps" id="lifecycle-steps">
    <span style="opacity:.3;font-size:.75rem">No invoice selected</span>
  </div>
</div>

<footer>
  <span class="ft-text">KEEPR — Recover the work safely. Not the human.</span>
  <div class="ft-links">
    <a href="#lab">Lab</a>
    <a href="#invoices">Invoices</a>
    <a href="#trace">Trace</a>
  </div>
</footer>

<script>
/* ── Particles ── */
(function(){
  const c=document.getElementById('particles');
  for(let i=0;i<25;i++){
    const p=document.createElement('div');
    p.className='particle';
    p.style.left=Math.random()*100+'%';
    p.style.animationDuration=(8+Math.random()*12)+'s';
    p.style.animationDelay=Math.random()*10+'s';
    p.style.width=p.style.height=(2+Math.random()*3)+'px';
    c.appendChild(p);
  }
})();

/* ── Scroll Reveal ── */
const obs=new IntersectionObserver(entries=>{
  entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('visible');obs.unobserve(e.target)}});
},{threshold:.15});
document.querySelectorAll('.reveal').forEach(el=>obs.observe(el));

/* ── Animated Counter ── */
function animateVal(el,to,suffix=''){
  const from=parseInt(el.textContent)||0;
  if(from===to)return;
  const dur=600;const start=performance.now();
  const step=t=>{
    const p=Math.min((t-start)/dur,1);
    const ease=1-Math.pow(1-p,3);
    el.textContent=Math.round(from+(to-from)*ease)+suffix;
    if(p<1)requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

let selected=null;
const badge=s=>{
  const m={COMPLETED:'b-COMPLETED',RECOVERED:'b-RECOVERED',ESCALATED:'b-ESCALATED',
           FROZEN:'b-FROZEN',PENDING:'b-PENDING',FAILED:'b-FAILED',PROCESSING:'b-PENDING'};
  return `<span class="badge ${m[s]||'b-PENDING'}">${s}</span>`;
};

const refresh=async()=>{
  try{
    const r=await fetch('/api/worker/status');
    if(!r.ok)return;
    const d=await r.json();
    const c=d.counts||{};
    const pending=c.pending??50;
    const completed=(c.completed||0)+(c.recovered||0);
    const recovered=c.recovered??0;
    const escalated=c.escalated??0;
    const frozen=c.frozen??0;
    const total=50;
    const rate=total>0?Math.round(((total-escalated)/total)*100):0;

    animateVal(document.getElementById('v-pending'),pending);
    animateVal(document.getElementById('v-completed'),completed);
    animateVal(document.getElementById('v-recovered'),recovered);
    animateVal(document.getElementById('v-escalated'),escalated);
    animateVal(document.getElementById('v-frozen'),frozen);
    animateVal(document.getElementById('v-rate'),rate,'%');

    document.getElementById('bar-pending').style.width=(pending/total*100)+'%';
    document.getElementById('bar-completed').style.width=(completed/total*100)+'%';
    document.getElementById('bar-recovered').style.width=(recovered/total*100)+'%';
    document.getElementById('bar-escalated').style.width=(escalated/total*100)+'%';
    document.getElementById('bar-frozen').style.width=(frozen/total*100)+'%';
    document.getElementById('bar-rate').style.width=rate+'%';

    const body=document.getElementById('inv-body');
    body.innerHTML='';
    const invs=d.invoices||{};
    for(const[iid,info]of Object.entries(invs)){
      const st=info.status||'PENDING';
      const sel=selected===iid?' selected':'';
      body.innerHTML+=`<tr class="${sel}"><td>${iid}</td><td>${badge(st)}</td>`+
        `<td>${info.attempts||0}</td><td>${info.recovery_mode||'—'}</td>`+
        `<td><button class="trace-btn" onclick="selectInv('${iid}')">trace</button></td></tr>`;
    }
    document.getElementById('invoice-count').textContent=Object.keys(invs).length+' records';
    if(selected&&invs[selected])renderLifecycle(invs[selected].trace||[]);
  }catch(e){}
};

const renderLifecycle=trace=>{
  const steps=document.getElementById('lifecycle-steps');
  const label=document.querySelector('.lifecycle-label');
  if(!trace.length){
    label.textContent='Select an invoice to view its recovery journey';
    steps.innerHTML='<span style="opacity:.3;font-size:.75rem">No invoice selected</span>';
    return;
  }
  label.textContent='Recovery journey — verified, not trusted';
  const classFor=e=>{
    if(e.includes('FAIL')||e.includes('BLOCKED')||e.includes('REJECT'))return 'fail';
    if(e.includes('COMPLETED')||e.includes('VERIFIED'))return 'ok';
    if(e.includes('RECOVER')||e.includes('policy:'))return 'rec';
    if(e.includes('ESCALAT'))return 'esc';
    if(e.includes('FROZEN')||e.includes('FREEZE'))return 'frozen';
    return '';
  };
  steps.innerHTML='';
  trace.forEach((t,i)=>{
    const cls=classFor(t.event);
    const delay=i*80;
    if(i>0){
      const arrow=document.createElement('span');
      arrow.className='arrow';
      arrow.textContent='→';
      steps.appendChild(arrow);
    }
    const s=document.createElement('span');
    s.className='step '+cls;
    s.style.animationDelay=delay+'ms';
    s.textContent=t.state+':'+t.event;
    steps.appendChild(s);
  });
};

const selectInv=iid=>{
  selected=iid;
  document.querySelector('.lifecycle-label').textContent='Tracing: '+iid;
  refresh();
};

const runWorker=async()=>{
  const btn=document.querySelector('.btn-primary');
  btn.textContent='Running...';
  btn.style.pointerEvents='none';
  await fetch('/api/worker/run',{method:'POST'});
  btn.textContent='Run 50 Invoices';
  btn.style.pointerEvents='';
  refresh();
};

const resetWorker=async()=>{
  await fetch('/api/worker/reset',{method:'POST'});
  selected=null;
  document.querySelector('.lifecycle-label').textContent='Select an invoice to view its recovery journey';
  document.getElementById('lifecycle-steps').innerHTML='<span style="opacity:.3;font-size:.75rem">No invoice selected</span>';
  refresh();
};

const inject=async(btn,iid,mode)=>{
  btn.classList.add('injected');
  setTimeout(()=>btn.classList.remove('injected'),600);
  const msg=document.getElementById('lab-msg');
  msg.className='lab-msg active';
  msg.textContent='Injecting '+mode+' into '+iid+'...';
  await fetch('/api/worker/attack',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({invoice_id:iid,mode})});
  msg.textContent='Injected '+mode+'. Run worker to see recovery.';
  setTimeout(()=>{msg.className='lab-msg';msg.textContent=''},3000);
};

const authorityAttack=async(btn)=>{
  btn.classList.add('injected');
  setTimeout(()=>btn.classList.remove('injected'),600);
  const msg=document.getElementById('lab-msg');
  msg.className='lab-msg active';
  msg.textContent='Authority widening attack sent...';
  await fetch('/api/worker/authority-attack',{method:'POST'});
  msg.textContent='Blocked. Recovery cannot widen authority.';
  setTimeout(()=>{msg.className='lab-msg';msg.textContent=''},3000);
};

const falseCompletion=async(btn)=>{
  btn.classList.add('injected');
  setTimeout(()=>btn.classList.remove('injected'),600);
  const msg=document.getElementById('lab-msg');
  msg.className='lab-msg active';
  msg.textContent='False completion: agent says DONE, verifier says NOT...';
  await fetch('/api/worker/false-completion',{method:'POST'});
  msg.textContent='Rejected. Verifier froze the item.';
  setTimeout(()=>{msg.className='lab-msg';msg.textContent=''},3000);
};

const oscillation=async(btn)=>{
  btn.classList.add('injected');
  setTimeout(()=>btn.classList.remove('injected'),600);
  const msg=document.getElementById('lab-msg');
  msg.className='lab-msg active';
  msg.textContent='Oscillation attack: alternating failures...';
  await fetch('/api/worker/oscillation',{method:'POST'});
  msg.textContent='Bounded. Paranoia bound triggered ESCALATE.';
  setTimeout(()=>{msg.className='lab-msg';msg.textContent=''},3000);
};

setInterval(refresh,1000);
refresh();
</script>
</body>
</html>"""


def render_dashboard() -> str:
    return DASHBOARD_HTML
