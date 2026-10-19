import {
  Activity,
  ArrowRight,
  BarChart3,
  Bot,
  Boxes,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  FileCheck2,
  Fingerprint,
  FlaskConical,
  GitBranch,
  LockKeyhole,
  Menu,
  Network,
  Radar,
  Shield,
  ShieldCheck,
  Sparkles,
  X,
  type LucideIcon,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { BrandMark } from '../components/layout/BrandMark'
import { DigitalTwinDemo } from '../components/marketing/DigitalTwinDemo'
import { isDevelopmentSession } from '../lib/auth'
import { getSession } from '../services/sessionApi'

const capabilities = [
  {
    icon: FlaskConical,
    title: 'Red Agent Simulation',
    copy: 'Run controlled attack scenarios inside an isolated synthetic cloud range.',
    tone: 'red',
  },
  {
    icon: Radar,
    title: 'Anomaly Detection',
    copy: 'Identify suspicious activity using the range’s IsolationForest detection pipeline.',
    tone: 'blue',
  },
  {
    icon: GitBranch,
    title: 'MITRE ATT&CK Mapping',
    copy: 'Correlate observed stages to techniques with traceable supporting evidence.',
    tone: 'violet',
  },
  {
    icon: ShieldCheck,
    title: 'Blue Agent Response',
    copy: 'Generate deterministic, policy-governed response recommendations.',
    tone: 'green',
  },
  {
    icon: Boxes,
    title: 'Interactive Digital Twin',
    copy: 'Explore assets, attack paths, blast radius, and simulated mitigations.',
    tone: 'blue',
  },
  {
    icon: FileCheck2,
    title: 'Reports & Evaluation',
    copy: 'Compare strategies with reproducible results and tamper-evident audit trails.',
    tone: 'orange',
  },
]

const workflow = [
  ['1', 'Red Agent', 'Simulate a controlled attack', FlaskConical],
  ['2', 'Telemetry', 'Capture synthetic evidence', Activity],
  ['3', 'Detection', 'Identify anomalous behavior', Radar],
  ['4', 'Correlation', 'Map evidence to ATT&CK', GitBranch],
  ['5', 'Blue Agent', 'Recommend a response', Bot],
  ['6', 'Policy Approval', 'Apply role-based gates', LockKeyhole],
  ['7', 'Mitigation', 'Execute in simulation', ShieldCheck],
  ['8', 'Twin Verification', 'Verify and visualize', Boxes],
] as const

const highlights: { icon: LucideIcon; top: string; bottom: string }[] = [
  { icon: Network, top: 'Simulated', bottom: 'Environment' },
  { icon: BrainCircuit, top: 'AI-assisted', bottom: 'Detection' },
  { icon: Shield, top: 'Autonomous', bottom: 'Response' },
  { icon: Boxes, top: 'Interactive', bottom: 'Digital Twin' },
  { icon: Fingerprint, top: 'MITRE ATT&CK', bottom: 'Mapping' },
  { icon: BarChart3, top: 'Reports &', bottom: 'Evaluation' },
]

export function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [launching, setLaunching] = useState(false)
  const navigate = useNavigate()

  async function launchConsole() {
    setLaunching(true)
    try {
      const session = await getSession()
      void navigate(
        session.authenticated && !isDevelopmentSession(session) ? '/app' : '/login?next=%2Fapp',
      )
    } catch {
      void navigate('/login?next=%2Fapp')
    }
  }

  return (
    <div className="marketing-shell">
      <header className="marketing-nav">
        <Link className="marketing-brand" to="/" aria-label="AegisArena home">
          <BrandMark /> <strong>AegisArena</strong>
        </Link>
        <nav
          className={menuOpen ? 'marketing-links is-open' : 'marketing-links'}
          aria-label="Public navigation"
        >
          <a
            href="#platform"
            onClick={() => {
              setMenuOpen(false)
            }}
          >
            Platform
          </a>
          <a
            href="#features"
            onClick={() => {
              setMenuOpen(false)
            }}
          >
            Features
          </a>
          <a
            href="#how-it-works"
            onClick={() => {
              setMenuOpen(false)
            }}
          >
            How it works
          </a>
          <a
            href="#architecture"
            onClick={() => {
              setMenuOpen(false)
            }}
          >
            Architecture
          </a>
          <a
            href="#transparency"
            onClick={() => {
              setMenuOpen(false)
            }}
          >
            Security
          </a>
        </nav>
        <div className="marketing-actions">
          <Link className="public-btn public-btn-ghost nav-signin" to="/login">
            Sign in
          </Link>
          <button
            className="public-btn public-btn-primary nav-launch"
            onClick={() => void launchConsole()}
            disabled={launching}
          >
            {launching ? 'Checking session…' : 'Launch console'} <ArrowRight aria-hidden="true" />
          </button>
          <button
            className="public-menu"
            onClick={() => {
              setMenuOpen((value) => !value)
            }}
            aria-label="Toggle navigation"
            aria-expanded={menuOpen}
          >
            {menuOpen ? <X /> : <Menu />}
          </button>
        </div>
      </header>

      <main>
        <section className="hero-section" id="platform">
          <div className="hero-copy">
            <p className="public-eyebrow">
              <Sparkles aria-hidden="true" /> Autonomous cloud cyber range
            </p>
            <h1>
              Simulate Threats.
              <br />
              <span>Visualize Defense.</span>
            </h1>
            <p className="hero-lede">
              AegisArena combines controlled attack simulation, anomaly detection, coordinated
              defensive agents, and a synchronized Digital Twin to visualize cyber threats and
              evaluate security responses.
            </p>
            <div className="hero-actions">
              <button
                className="public-btn public-btn-primary public-btn-large"
                onClick={() => void launchConsole()}
                disabled={launching}
              >
                Launch AegisArena <ArrowRight aria-hidden="true" />
              </button>
              <a className="public-btn public-btn-ghost public-btn-large" href="#features">
                Explore platform
              </a>
            </div>
            <div className="hero-trust">
              <span>
                <CheckCircle2 /> Simulation only
              </span>
              <span>
                <CheckCircle2 /> Policy governed
              </span>
              <span>
                <CheckCircle2 /> Fully auditable
              </span>
            </div>
          </div>
          <div className="hero-visual">
            <DigitalTwinDemo />
          </div>
        </section>

        <section className="capability-strip" aria-label="Platform highlights">
          {highlights.map(({ icon: Icon, top, bottom }) => (
            <div key={top}>
              <Icon aria-hidden="true" />
              <span>
                {top}
                <br />
                {bottom}
              </span>
            </div>
          ))}
        </section>

        <section className="public-section" id="features">
          <div className="section-heading">
            <p className="public-eyebrow">Core capabilities</p>
            <h2>One range. The complete defense lifecycle.</h2>
            <p>
              Experiment safely with the actual components that power AegisArena’s cloud-security
              console.
            </p>
          </div>
          <div className="capability-grid">
            {capabilities.map(({ icon: Icon, title, copy, tone }) => (
              <article className="capability-card" key={title}>
                <span className={`capability-icon is-${tone}`}>
                  <Icon aria-hidden="true" />
                </span>
                <h3>{title}</h3>
                <p>{copy}</p>
                <a href="#how-it-works">
                  See it in the workflow <ChevronRight />
                </a>
              </article>
            ))}
          </div>
        </section>

        <section className="public-section workflow-section" id="how-it-works">
          <div className="section-heading">
            <p className="public-eyebrow">How AegisArena works</p>
            <h2>From attack signal to verified resilience.</h2>
            <p>Every stage stays explainable, reversible, and grounded in synthetic evidence.</p>
          </div>
          <div className="workflow-line">
            {workflow.map(([number, title, copy, Icon]) => (
              <article className="workflow-step" key={title}>
                <span className="workflow-number">{number}</span>
                <span className="workflow-icon">
                  <Icon aria-hidden="true" />
                </span>
                <h3>{title}</h3>
                <p>{copy}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="showcase-section" id="architecture">
          <div className="showcase-copy">
            <p className="public-eyebrow">Interactive cloud Digital Twin</p>
            <h2>See the environment change as defense unfolds.</h2>
            <p>
              Follow attack progression through infrastructure relationships, inspect the evidence
              behind a response, preview proposed containment, and verify the resulting simulated
              state.
            </p>
            <ul>
              <li>
                <CheckCircle2 /> Trace attack paths and affected assets
              </li>
              <li>
                <CheckCircle2 /> Distinguish proposed and executed actions
              </li>
              <li>
                <CheckCircle2 /> Verify mitigation and rollback outcomes
              </li>
            </ul>
            <button className="public-btn public-btn-primary" onClick={() => void launchConsole()}>
              Open Digital Twin <ArrowRight />
            </button>
          </div>
          <div className="showcase-frame">
            <DigitalTwinDemo />
          </div>
        </section>

        <section className="transparency-section" id="transparency">
          <div>
            <span className="transparency-icon">
              <ShieldCheck />
            </span>
            <p className="public-eyebrow">Security & transparency</p>
            <h2>A safe place to test hard decisions.</h2>
          </div>
          <p>
            AegisArena operates in simulation-only mode. Its cloud estate, telemetry, attack
            activity, and mitigations are synthetic. It does not claim live production telemetry or
            perform real-world remediation.
          </p>
          <div className="transparency-points">
            <span>
              <strong>Backend verified</strong>Authorization is enforced by the API.
            </span>
            <span>
              <strong>Role based</strong>Viewer, Analyst, and Admin boundaries stay explicit.
            </span>
            <span>
              <strong>Auditable</strong>Decisions and simulated actions retain evidence.
            </span>
          </div>
        </section>

        <section className="final-cta">
          <div>
            <p className="public-eyebrow">Enter the range</p>
            <h2>Ready to explore autonomous cloud defense?</h2>
            <p>
              Move from controlled attack to explainable, verified response in one connected
              experience.
            </p>
          </div>
          <div>
            <button
              className="public-btn public-btn-primary public-btn-large"
              onClick={() => void launchConsole()}
            >
              Launch console <ArrowRight />
            </button>
            <a className="public-btn public-btn-ghost public-btn-large" href="#features">
              Explore capabilities
            </a>
          </div>
        </section>
      </main>

      <footer className="marketing-footer">
        <div>
          <span className="marketing-brand">
            <BrandMark /> <strong>AegisArena</strong>
          </span>
          <p>Autonomous cloud cyber range for simulation, detection, response, and evaluation.</p>
        </div>
        <nav aria-label="Footer navigation">
          <a href="#platform">Platform</a>
          <a href="#features">Capabilities</a>
          <a href="#how-it-works">How it works</a>
          <a href="#transparency">Security</a>
        </nav>
        <p>Academic cloud computing project · Simulation only</p>
      </footer>
    </div>
  )
}
