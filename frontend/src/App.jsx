import { useState } from 'react'

const API = 'http://localhost:8000'

const LABELS = {
  before_after: 'Before / After',
  quick_hit: 'Quick Hit',
  timelapse: 'Timelapse',
  full_story: 'Full Story',
  slow_build: 'Slow Build',
}

function reelLabel(url) {
  const name = url.split('/').pop().replace('.mp4', '').replace(/^\d+_/, '')
  return LABELS[name] || name
}

export default function App() {
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('idle')
  const [reels, setReels] = useState([])
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)

  function pickFile(f) {
    if (!f) return
    setFile(f)
    setReels([])
    setStatus('idle')
    setError('')
  }

  async function generate() {
    if (!file) return
    setStatus('uploading')
    setError('')
    const form = new FormData()
    form.append('video', file)
    try {
      const res = await fetch(`${API}/projects`, { method: 'POST', body: form })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Something went wrong')
      setReels(data.reels)
      setStatus('done')
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
          disabled={!file || status === 'uploading'}
          className="mt-6 w-full rounded-xl bg-violet-600 py-3 font-semibold transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {status === 'uploading' ? 'Making your reels...' : 'Generate 5 reels'}
        </button>

        {status === 'uploading' && (
          <div className="mt-4 h-1 w-full overflow-hidden rounded bg-neutral-800">
            <div className="h-full w-1/3 animate-pulse rounded bg-violet-500" />
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