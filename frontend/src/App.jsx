import { useState } from 'react'

const API = 'http://localhost:8000'

const LABELS = {
  before_after: 'Before / After',
  quick_hit: 'Quick Hit',
  timelapse: 'Timelapse',
  full_story: 'Full Story',
  slow_build: 'Slow Build',
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function reelLabel(url) {
  const name = url.split('/').pop().replace('.mp4', '').replace(/^\d+_/, '')
  return LABELS[name] || name
}

export default function App() {
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('idle')
  const [reels, setReels] = useState([])
  const [progress, setProgress] = useState(0)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)

  const working = status === 'working'

  function pickFile(f) {
    if (!f) return
    setFile(f)
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

  return (
    <div className="min-h-screen bg-neutral-950 text-white">
      <div className="mx-auto max-w-5xl px-6 py-12">
        <header className="mb-10">
          <h1 className="text-4xl font-bold tracking-tight">ClipFlow</h1>
          <p className="mt-2 text-neutral-400">
            Drop in a full session. Get 5 transformation reels back.
          </p>
        </header>

        <label
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files[0]) }}
          className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-12 text-center transition ${
            dragging ? 'border-violet-400 bg-violet-500/10' : 'border-neutral-700 hover:border-neutral-500'
          }`}
        >
          <input type="file" accept="video/*" className="hidden" onChange={(e) => pickFile(e.target.files[0])} />
          <p className="text-lg font-medium">{file ? file.name : 'Drag a video here, or click to choose'}</p>
          <p className="mt-1 text-sm text-neutral-500">.mov or .mp4</p>
        </label>

        <button
          onClick={generate}
          disabled={!file || working}
          className="mt-6 w-full rounded-xl bg-violet-600 py-3 font-semibold transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {working ? 'Working...' : 'Generate 5 reels'}
        </button>

        {working && (
          <div className="mt-6">
            <div className="mb-2 flex justify-between text-sm text-neutral-400">
              <span>{message}</span>
              <span>{Math.round(progress * 100)}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-neutral-800">
              <div
                className="h-full rounded-full bg-violet-500 transition-all duration-500"
                style={{ width: `${Math.round(progress * 100)}%` }}
              />
            </div>
          </div>
        )}

        {error && <p className="mt-4 rounded-lg bg-red-500/10 p-3 text-red-400">{error}</p>}

        {reels.length > 0 && (
          <section className="mt-12">
            <h2 className="mb-6 text-2xl font-semibold">Your reels</h2>
            <div className="grid grid-cols-2 gap-6 md:grid-cols-3 lg:grid-cols-5">
              {reels.map((url) => (
                <div key={url} className="flex flex-col">
                  <video src={`${API}${url}`} controls className="aspect-[9/16] w-full rounded-xl bg-black object-cover" />
                  <p className="mt-2 text-sm font-medium">{reelLabel(url)}</p>
                  <a href={`${API}${url}`} target="_blank" rel="noreferrer" className="mt-1 text-sm text-violet-400 hover:text-violet-300">
                    Open / Download
                  </a>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}