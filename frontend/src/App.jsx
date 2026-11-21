import { useState } from 'react'

const API = 'http://localhost:8000'

const STYLES = {
  before_after: 'Before / After',
  quick_hit: 'Quick Hit',
  timelapse: 'Timelapse',
  full_story: 'Full Story',
  slow_build: 'Slow Build',
}

const STEPS = ['Upload', 'Analyze footage', 'Build reels', 'Done']

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function reelInfo(url) {
  const file = url.split('/').pop()
  const key = file.replace('.mp4', '').replace(/^\d+_/, '')
  return { file, label: STYLES[key] || key }
}

function formatSize(bytes) {
  return bytes > 1e9 ? `${(bytes / 1e9).toFixed(1)} GB` : `${(bytes / 1e6).toFixed(1)} MB`
}

function stageFor(status, progress) {
  if (status === 'done') return 3
  if (progress >= 0.2) return 2
  if (progress > 0) return 1
  return 0
}

async function downloadReel(url, file) {
  const res = await fetch(`${API}${url}`)
  const blob = await res.blob()
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `clipflow-${file}`
  link.click()
  URL.revokeObjectURL(link.href)
}

/* ---------- Icons ---------- */

function UploadIcon({ className }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M12 16V4m0 0l-4 4m4-4l4 4" />
      <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
    </svg>
  )
}

function DownloadIcon({ className }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M12 4v12m0 0l-4-4m4 4l4-4" />
      <path d="M4 18v.5A1.5 1.5 0 005.5 20h13a1.5 1.5 0 001.5-1.5V18" />
    </svg>
  )
}

function Spinner({ className }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={`animate-spin ${className}`}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 00-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

function Logo() {
  return (
    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-linear-to-br from-violet-500 to-fuchsia-500 shadow-lg shadow-violet-500/30">
      <svg viewBox="0 0 24 24" className="ml-0.5 h-5 w-5 fill-white"><path d="M8 5v14l11-7z" /></svg>
    </div>
  )
}

/* ---------- Pieces ---------- */

function Stepper({ stage }) {
  return (
    <ol className="flex flex-wrap items-center gap-2 text-xs">
      {STEPS.map((step, i) => (
        <li key={step} className="flex items-center gap-2">
          <span
            className={`flex h-6 w-6 items-center justify-center rounded-full border text-[11px] font-semibold transition ${
              i < stage
                ? 'border-violet-500 bg-violet-500 text-white'
                : i === stage
                ? 'border-violet-400 text-violet-300'
                : 'border-white/15 text-neutral-500'
            }`}
          >
            {i < stage ? '✓' : i + 1}
          </span>
          <span className={i <= stage ? 'text-neutral-200' : 'text-neutral-500'}>{step}</span>
          {i < STEPS.length - 1 && <span className="mx-1 h-px w-6 bg-white/10 sm:w-10" />}
        </li>
      ))}
    </ol>
  )
}

function ReelCard({ url }) {
  const { file, label } = reelInfo(url)
  const [duration, setDuration] = useState(null)
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      await downloadReel(url, file)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="group">
      <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-black shadow-lg transition duration-300 group-hover:-translate-y-1 group-hover:border-violet-500/50 group-hover:shadow-violet-500/20">
        <video
          src={`${API}${url}`}
          controls
          playsInline
          onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
          className="aspect-[9/16] w-full object-cover"
        />
        {duration && (
          <span className="pointer-events-none absolute left-2 top-2 rounded-full bg-black/60 px-2 py-0.5 text-[11px] font-medium text-white backdrop-blur">
            {Math.round(duration)}s
          </span>
        )}
      </div>
      <div className="mt-3 flex items-center justify-between">
        <p className="text-sm font-medium text-neutral-200">{label}</p>
        <button
          onClick={save}
          title="Download"
          className="rounded-lg p-1.5 text-neutral-400 transition hover:bg-white/10 hover:text-white"
        >
          {saving ? <Spinner className="h-4 w-4" /> : <DownloadIcon className="h-4 w-4" />}
        </button>
      </div>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div>
      <div className="aspect-[9/16] w-full animate-pulse rounded-2xl border border-white/5 bg-white/[0.04]" />
      <div className="mt-3 h-4 w-24 animate-pulse rounded bg-white/[0.06]" />
    </div>
  )
}

/* ---------- Page ---------- */

export default function App() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState('')
  const [status, setStatus] = useState('idle')
  const [reels, setReels] = useState([])
  const [progress, setProgress] = useState(0)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)

  const working = status === 'working'

  function pickFile(f) {
    if (!f) return
    if (preview) URL.revokeObjectURL(preview)
    setFile(f)
    setPreview(URL.createObjectURL(f))
    setReels([])
    setStatus('idle')
    setError('')
    setProgress(0)
  }

  function reset() {
    if (preview) URL.revokeObjectURL(preview)
    setFile(null)
    setPreview('')
    setReels([])
    setStatus('idle')
    setError('')
    setProgress(0)
  }

  async function generate() {
    if (!file) return
    setStatus('working')
    setError('')
    setReels([])
    setProgress(0)
    setMessage('Uploading video...')

    const form = new FormData()
    form.append('video', file)

    try {
      const res = await fetch(`${API}/projects`, { method: 'POST', body: form })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Upload failed')

      // Check in with the backend every second until the job finishes
      while (true) {
        await sleep(1000)
        const poll = await fetch(`${API}/projects/${data.project_id}`)
        const job = await poll.json()
        if (!poll.ok) throw new Error(job.detail || 'Lost track of the job')

        setProgress(job.progress)
        setMessage(job.message)
        setReels(job.reels)

        if (job.status === 'error') throw new Error(job.message)
        if (job.status === 'done') {
          if (job.reels.length === 0) setError("Couldn't find enough good footage to make a reel.")
          setStatus('done')
          break
        }
      }
    } catch (err) {
      setError(err.message)
      setStatus('error')
    }
  }

  const slots = working ? Array.from({ length: 5 }, (_, i) => reels[i]) : reels

  return (
    <div className="relative min-h-screen overflow-hidden bg-neutral-950 text-white">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-[600px]"
        style={{ background: 'radial-gradient(ellipse at top, rgba(139, 92, 246, 0.22), transparent 60%)' }}
      />

      <div className="relative mx-auto max-w-6xl px-6 pb-24">
        <nav className="flex items-center justify-between py-6">
          <div className="flex items-center gap-3">
            <Logo />
            <span className="text-2xl font-bold tracking-tight">ClipFlow</span>
            <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[11px] font-medium text-violet-300">
              Beta
            </span>
          </div>
        </nav>

        <header className="mx-auto mt-10 max-w-2xl text-center">
          <h1 className="bg-linear-to-b from-white to-neutral-400 bg-clip-text text-4xl font-bold tracking-tight text-transparent sm:text-6xl">
            Stop editing.
            <br />
            Start posting.
          </h1>
          <p className="mt-5 text-lg text-neutral-400">
            Upload any transformation video and get 5 edited reels back in minutes.
            All the editing's done for you.
          </p>
        </header>

        <div className="mx-auto mt-10 max-w-3xl rounded-3xl border border-white/10 bg-white/[0.03] p-6 shadow-2xl backdrop-blur">
          {!file ? (
            <label
              onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => { e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files[0]) }}
              className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-14 text-center transition ${
                dragging ? 'border-violet-400 bg-violet-500/10' : 'border-white/10 hover:border-white/25 hover:bg-white/[0.02]'
              }`}
            >
              <input type="file" accept="video/*" className="hidden" onChange={(e) => pickFile(e.target.files[0])} />
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-500/10 text-violet-300">
                <UploadIcon className="h-6 w-6" />
              </div>
              <p className="mt-4 text-lg font-medium">Drop your video here</p>
              <p className="mt-1 text-sm text-neutral-500">or click to browse · MOV or MP4</p>
            </label>
          ) : (
            <div className="flex items-center gap-4 rounded-2xl border border-white/10 bg-black/30 p-3">
              <video src={preview} muted className="h-20 w-32 rounded-xl bg-black object-cover" />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{file.name}</p>
                <p className="text-sm text-neutral-500">{formatSize(file.size)}</p>
              </div>
              {!working && (
                <button
                  onClick={reset}
                  className="rounded-lg border border-white/10 px-3 py-1.5 text-sm text-neutral-300 transition hover:bg-white/10"
                >
                  Change
                </button>
              )}
            </div>
          )}

          <button
            onClick={generate}
            disabled={!file || working}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-linear-to-r from-violet-600 to-fuchsia-600 py-3.5 font-semibold shadow-lg shadow-violet-600/20 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {working && <Spinner className="h-4 w-4" />}
            {working ? 'Working on it...' : 'Generate 5 reels'}
          </button>

          {working && (
            <div className="mt-6 space-y-4">
              <Stepper stage={stageFor(status, progress)} />
              <div>
                <div className="mb-2 flex justify-between text-sm">
                  <span className="text-neutral-300">{message}</span>
                  <span className="tabular-nums text-neutral-500">{Math.round(progress * 100)}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-white/5">
                  <div
                    className="h-full rounded-full bg-linear-to-r from-violet-500 to-fuchsia-500 transition-all duration-500"
                    style={{ width: `${Math.round(progress * 100)}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {error && (
            <p className="mt-5 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>
          )}
        </div>

        {slots.length > 0 && (
          <section className="mt-16">
            <div className="mb-6 flex items-end justify-between">
              <div>
                <h2 className="text-2xl font-semibold tracking-tight">Your reels</h2>
                <p className="mt-1 text-sm text-neutral-500">
                  {working ? 'Reels appear here as they finish.' : `${reels.length} reels ready to post.`}
                </p>
              </div>
              {status === 'done' && (
                <button
                  onClick={reset}
                  className="rounded-lg border border-white/10 px-4 py-2 text-sm text-neutral-300 transition hover:bg-white/10"
                >
                  Start over
                </button>
              )}
            </div>
            <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-5">
              {slots.map((url, i) => (url ? <ReelCard key={url} url={url} /> : <SkeletonCard key={`skeleton-${i}`} />))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}