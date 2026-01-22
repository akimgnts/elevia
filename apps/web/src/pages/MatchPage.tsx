import { useState } from 'react'
import { Link } from 'react-router-dom'

interface ResultItem {
  offer_id: string
  score: number
  breakdown: Record<string, number>
  reasons: string[]
}

interface MatchResponse {
  profile_id: string
  threshold: number
  results: ResultItem[]
  message: string | null
}

export default function MatchPage() {
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<MatchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const runMatch = async () => {
    setLoading(true)
    setError(null)
    setResponse(null)

    try {
      const [profileRes, offersRes] = await Promise.all([
        fetch('/fixtures/profile_demo.json'),
        fetch('/fixtures/offers_demo.json'),
      ])

      if (!profileRes.ok || !offersRes.ok) {
        throw new Error('Erreur chargement fixtures')
      }

      const profile = await profileRes.json()
      const offers = await offersRes.json()

      const matchRes = await fetch('/v1/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile, offers }),
      })

      if (!matchRes.ok) {
        const text = await matchRes.text()
        throw new Error(`API error ${matchRes.status}: ${text}`)
      }

      const data: MatchResponse = await matchRes.json()
      setResponse(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <nav style={{ marginBottom: '2rem' }}>
        <Link to="/" style={{ color: '#666', textDecoration: 'none' }}>
          ← Accueil
        </Link>
      </nav>

      <h1 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>
        Match Runner
      </h1>
      <p style={{ color: '#666', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
        Quelles offres VIE matchent avec le profil demo ?
      </p>

      <button
        onClick={runMatch}
        disabled={loading}
        style={{
          padding: '0.75rem 1.5rem',
          backgroundColor: loading ? '#94a3b8' : '#0f172a',
          color: 'white',
          border: 'none',
          borderRadius: '6px',
          cursor: loading ? 'not-allowed' : 'pointer',
          fontSize: '0.9rem',
        }}
      >
        {loading ? 'Matching...' : 'Lancer le match'}
      </button>

      {error && (
        <div
          style={{
            marginTop: '1.5rem',
            padding: '1rem',
            backgroundColor: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: '6px',
            color: '#991b1b',
            fontSize: '0.9rem',
          }}
        >
          {error}
        </div>
      )}

      {response && (
        <section style={{ marginTop: '2rem' }}>
          <div
            style={{
              display: 'flex',
              gap: '1rem',
              marginBottom: '1rem',
              fontSize: '0.85rem',
              color: '#666',
            }}
          >
            <span>Profil: {response.profile_id}</span>
            <span>Seuil: {response.threshold}</span>
            <span>Résultats: {response.results.length}</span>
          </div>

          {response.message && (
            <p
              style={{
                padding: '1rem',
                backgroundColor: '#f8fafc',
                borderRadius: '6px',
                color: '#475569',
                fontSize: '0.9rem',
              }}
            >
              {response.message}
            </p>
          )}

          {response.results.length > 0 && (
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {response.results.map((item) => (
                <li
                  key={item.offer_id}
                  style={{
                    padding: '1rem',
                    marginBottom: '0.75rem',
                    backgroundColor: '#f8fafc',
                    borderRadius: '6px',
                    border: '1px solid #e2e8f0',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '0.5rem',
                    }}
                  >
                    <strong style={{ fontSize: '0.95rem' }}>
                      {item.offer_id}
                    </strong>
                    <span
                      style={{
                        backgroundColor: '#0f172a',
                        color: 'white',
                        padding: '0.25rem 0.75rem',
                        borderRadius: '999px',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                      }}
                    >
                      {item.score}%
                    </span>
                  </div>

                  {item.reasons.length > 0 && (
                    <ul
                      style={{
                        margin: '0.5rem 0 0 0',
                        padding: '0 0 0 1.25rem',
                        fontSize: '0.85rem',
                        color: '#475569',
                      }}
                    >
                      {item.reasons.map((reason, idx) => (
                        <li key={idx} style={{ marginBottom: '0.25rem' }}>
                          {reason}
                        </li>
                      ))}
                    </ul>
                  )}

                  <div
                    style={{
                      marginTop: '0.75rem',
                      display: 'flex',
                      gap: '0.5rem',
                      flexWrap: 'wrap',
                      fontSize: '0.75rem',
                      color: '#64748b',
                    }}
                  >
                    {Object.entries(item.breakdown).map(([key, val]) => (
                      <span
                        key={key}
                        style={{
                          backgroundColor: '#e2e8f0',
                          padding: '0.2rem 0.5rem',
                          borderRadius: '4px',
                        }}
                      >
                        {key}: {(val * 100).toFixed(0)}%
                      </span>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </main>
  )
}
