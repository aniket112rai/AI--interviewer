import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useLocalParticipant,
  useTranscriptions,
  useVoiceAssistant,
} from '@livekit/components-react'
import { apiRequest } from '../api/client.js'
import { useAuth } from '../auth/AuthContext.jsx'

const captureOptions = {
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
}

function LiveInterview({ onEnd, durationMin, identity }) {
  const { localParticipant } = useLocalParticipant()
  const assistant = useVoiceAssistant()
  const transcriptions = useTranscriptions()
  const [muted, setMuted] = useState(false)
  const [remaining, setRemaining] = useState(durationMin * 60)
  const [confirmEnd, setConfirmEnd] = useState(false)

  useEffect(() => {
    const timer = window.setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (remaining === 0) onEnd(false)
  }, [remaining, onEnd])

  async function toggleMute() {
    const next = !muted
    await localParticipant.setMicrophoneEnabled(!next, captureOptions)
    setMuted(next)
  }

  const state = assistant.state || 'listening'
  const transcript = transcriptions.slice(-12)
  return (
    <section className="mx-auto max-w-3xl rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-9">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-600">Live interview</p>
          <h1 className="mt-2 text-2xl font-semibold capitalize">{state}</h1>
        </div>
        <p className="rounded-full bg-slate-100 px-4 py-2 font-mono text-sm">{Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, '0')} left</p>
      </div>
      <div className={`my-7 flex h-24 items-center justify-center rounded-2xl ${state === 'speaking' ? 'bg-indigo-50' : 'bg-slate-50'}`}>
        <div className={`h-12 w-12 rounded-full ${state === 'speaking' ? 'animate-pulse bg-indigo-600' : state === 'thinking' ? 'bg-amber-400' : 'bg-emerald-500'}`} />
      </div>
      <div aria-live="polite" className="max-h-80 space-y-3 overflow-y-auto rounded-2xl border border-slate-100 bg-slate-50 p-4">
        {transcript.length === 0 ? <p className="text-sm text-slate-500">Your interview transcript will appear here.</p> : transcript.map((item, index) => (
          <p key={`${item.streamInfo?.id || index}-${index}`} className="text-sm leading-6 text-slate-700">
            <span className="mr-2 font-semibold text-indigo-700">{item.participantInfo.identity === identity ? 'You' : 'Interviewer'}</span>{item.text}
          </p>
        ))}
      </div>
      <div className="mt-6 flex flex-wrap gap-3">
        <button onClick={toggleMute} className="rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-800">{muted ? 'Unmute microphone' : 'Mute microphone'}</button>
        <button onClick={() => setConfirmEnd(true)} className="rounded-full bg-rose-600 px-5 py-3 text-sm font-semibold text-white hover:bg-rose-700">End interview</button>
      </div>
      {confirmEnd && <div role="dialog" aria-modal="true" aria-labelledby="end-title" className="fixed inset-0 z-20 grid place-items-center bg-slate-950/40 p-5">
        <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
          <h2 id="end-title" className="text-lg font-semibold">End this interview?</h2>
          <p className="mt-2 text-sm text-slate-600">Your conversation will be saved and the session will finish.</p>
          <div className="mt-5 flex justify-end gap-3">
            <button onClick={() => setConfirmEnd(false)} className="rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold">Keep going</button>
            <button onClick={() => onEnd(true, localParticipant)} className="rounded-full bg-rose-600 px-4 py-2 text-sm font-semibold text-white">End interview</button>
          </div>
        </div>
      </div>}
      <RoomAudioRenderer />
    </section>
  )
}

export default function VoiceLoop() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [devices, setDevices] = useState([])
  const [deviceId, setDeviceId] = useState('')
  const [micReady, setMicReady] = useState(false)
  const [micWorks, setMicWorks] = useState(false)
  const [level, setLevel] = useState(0)
  const [micError, setMicError] = useState('')
  const [call, setCall] = useState(null)
  const [duration, setDuration] = useState(15)
  const [loading, setLoading] = useState(true)
  const [sessionError, setSessionError] = useState('')
  const [connecting, setConnecting] = useState(false)
  const [connectionLost, setConnectionLost] = useState(false)
  const streamRef = useRef(null)
  const audioContextRef = useRef(null)
  const animationRef = useRef(null)
  const heardAudioRef = useRef(false)
  const endingRef = useRef(false)

  useEffect(() => {
    let active = true
    apiRequest(`/api/sessions/${sessionId}`)
      .then((item) => { if (active) setDuration(item.duration_min) })
      .catch((cause) => { if (active) setSessionError(cause.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [sessionId])

  const stopMeter = useCallback(() => {
    if (animationRef.current) cancelAnimationFrame(animationRef.current)
    animationRef.current = null
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    audioContextRef.current?.close()
    audioContextRef.current = null
  }, [])
  useEffect(() => () => stopMeter(), [stopMeter])

  const checkMicrophone = useCallback(async (requestedDevice = deviceId) => {
    stopMeter()
    setMicReady(false)
    setMicWorks(false)
    heardAudioRef.current = false
    setMicError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { ...captureOptions, ...(requestedDevice ? { deviceId: { exact: requestedDevice } } : {}) } })
      streamRef.current = stream
      const allDevices = await navigator.mediaDevices.enumerateDevices()
      const microphones = allDevices.filter((device) => device.kind === 'audioinput')
      setDevices(microphones)
      const activeId = requestedDevice || stream.getAudioTracks()[0]?.getSettings().deviceId || microphones[0]?.deviceId || ''
      setDeviceId(activeId)
      const context = new AudioContext()
      audioContextRef.current = context
      const source = context.createMediaStreamSource(stream)
      const analyser = context.createAnalyser()
      analyser.fftSize = 512
      source.connect(analyser)
      const samples = new Uint8Array(analyser.fftSize)
      const tick = () => {
        analyser.getByteTimeDomainData(samples)
        let squareSum = 0
        for (const sample of samples) {
          const value = (sample - 128) / 128
          squareSum += value * value
        }
        const rms = Math.sqrt(squareSum / samples.length)
        setLevel(Math.min(1, rms * 3))
        if (rms > 0.018 && !heardAudioRef.current) {
          heardAudioRef.current = true
          setMicWorks(true)
        }
        animationRef.current = requestAnimationFrame(tick)
      }
      tick()
      setMicReady(true)
    } catch (cause) {
      setMicError(cause instanceof Error ? cause.message : 'Microphone access failed. Check browser permissions and try again.')
    }
  }, [deviceId, stopMeter])

  async function startInterview() {
    setConnecting(true)
    setMicError('')
    try {
      const token = await apiRequest(`/api/sessions/${sessionId}/token`, { method: 'POST' })
      setCall(token)
      setConnectionLost(false)
      stopMeter()
    } catch (cause) {
      if (cause.status === 409) {
        navigate(`/sessions/${sessionId}/report`, { replace: true })
        return
      }
      setMicError(cause.message)
      setConnectionLost(true)
      setConnecting(false)
    }
  }

  const endInterview = useCallback(async (explicitEnd, participant) => {
    endingRef.current = true
    if (explicitEnd) {
      try {
        await participant?.publishData(new TextEncoder().encode('end_interview'), { reliable: true })
      } catch { /* disconnect still closes the room if the end signal cannot be sent */ }
    }
    navigate(`/sessions/${sessionId}/report`, { replace: true })
  }, [navigate, sessionId])

  if (loading) return <p className="text-sm text-slate-500">Loading interview…</p>

  if (sessionError) return <section className="mx-auto max-w-xl rounded-3xl border border-rose-200 bg-white p-7 shadow-sm sm:p-9"><h1 className="text-2xl font-semibold">Interview unavailable</h1><p role="alert" className="mt-3 text-sm leading-6 text-rose-700">{sessionError}</p><Link to="/dashboard" className="mt-6 inline-flex min-h-11 items-center rounded-full bg-indigo-600 px-5 py-3 text-sm font-semibold text-white">Back to dashboard</Link></section>

  if (connectionLost && !call) return (
    <section className="mx-auto max-w-xl rounded-3xl border border-amber-200 bg-white p-7 shadow-sm sm:p-9">
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-amber-700">Connection interrupted</p>
      <h1 className="mt-3 text-2xl font-semibold">Your interview can reconnect</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">{micError || 'The room connection was lost. Your saved conversation is still available.'} Reconnect to continue while the session is active.</p>
      <div className="mt-6 flex flex-wrap gap-3">
        <button disabled={connecting} onClick={startInterview} className="min-h-11 rounded-full bg-indigo-600 px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">{connecting ? 'Reconnecting…' : 'Reconnect to interview'}</button>
        <Link to={`/sessions/${sessionId}/report`} className="inline-flex min-h-11 items-center rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700">Go to report status</Link>
      </div>
    </section>
  )

  if (call) return <LiveKitRoom
    serverUrl={call.url}
    token={call.token}
    connect
    audio={{ ...captureOptions, ...(deviceId ? { deviceId: { exact: deviceId } } : {}) }}
    options={{ audioCaptureDefaults: captureOptions }}
    onConnected={() => setConnecting(false)}
    onDisconnected={() => {
      if (endingRef.current) navigate(`/sessions/${sessionId}/report`, { replace: true })
      else {
        setMicError('The room connection was lost. Your saved conversation is still available.')
        setConnectionLost(true)
        setCall(null)
      }
    }}
    onError={(cause) => { setMicError(cause.message); setConnectionLost(true); setCall(null); setConnecting(false) }}
    className="w-full"
  >
    <LiveInterview onEnd={endInterview} durationMin={duration} identity={user?.id} />
  </LiveKitRoom>

  return (
    <div className="mx-auto max-w-2xl">
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-600">Before we begin</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">Check your microphone</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">Allow microphone access and speak a few words. Use headphones and a quiet room for clearer audio.</p>
      <section className="mt-7 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm">
        <label className="block text-sm font-medium text-slate-700">Microphone
          <select value={deviceId} onChange={(event) => { setDeviceId(event.target.value); checkMicrophone(event.target.value) }} className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-4 py-3">
            <option value="">System default microphone</option>
            {devices.map((device, index) => <option key={device.deviceId || index} value={device.deviceId}>{device.label || `Microphone ${index + 1}`}</option>)}
          </select>
        </label>
        <button onClick={() => checkMicrophone()} className="mt-5 rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-800">{micReady ? 'Refresh microphone check' : 'Check microphone'}</button>
        <div className="mt-6">
          <div className="h-3 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-emerald-500 transition-[width]" style={{ width: `${Math.max(2, level * 100)}%` }} /></div>
          <p className="mt-2 text-xs text-slate-500">{!micReady ? 'Microphone permission is required before you can start.' : micWorks ? 'Microphone is picking up audio.' : 'Speak a few words to confirm your microphone is working.'}</p>
        </div>
        {micReady && level > 0.45 && <p className="mt-3 text-sm text-amber-700">Audio is peaking. Move the microphone slightly away and use a quieter room.</p>}
        {micError && <p role="alert" className="mt-4 text-sm text-rose-700">{micError}</p>}
        <div className="mt-7 flex flex-wrap gap-3">
          <button disabled={!micWorks || connecting} onClick={startInterview} className="rounded-full bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50">{connecting ? 'Connecting…' : 'Start interview'}</button>
          <Link to="/dashboard" className="rounded-full border border-slate-300 px-6 py-3 text-sm font-semibold text-slate-700">Back to dashboard</Link>
        </div>
      </section>
    </div>
  )
}
