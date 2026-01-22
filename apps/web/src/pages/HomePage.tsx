import { Link } from 'react-router-dom'

export default function HomePage() {
  return (
    <main style={{ padding: '2rem', maxWidth: '600px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '1.5rem', marginBottom: '1rem' }}>Elevia Compass</h1>
      <p style={{ color: '#666', marginBottom: '2rem' }}>
        Plateforme de matching VIE
      </p>
      <Link
        to="/match"
        style={{
          display: 'inline-block',
          padding: '0.75rem 1.5rem',
          backgroundColor: '#0f172a',
          color: 'white',
          textDecoration: 'none',
          borderRadius: '6px',
        }}
      >
        Lancer le Match Runner
      </Link>
    </main>
  )
}
