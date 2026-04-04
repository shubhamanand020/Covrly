import './Navbar.css'

const getInitials = (name = '') => {
  const tokens = String(name || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)

  if (!tokens.length) {
    return 'U'
  }

  const letters = tokens.slice(0, 2).map((token) => token.charAt(0).toUpperCase())
  return letters.join('')
}

function Navbar({ showBack = false, onBack, profileName = '', profileImageUrl = '', onOpenProfileMenu }) {
  const normalizedImage = String(profileImageUrl || '').trim()
  const initials = getInitials(profileName)

  return (
    <header className="navbar">
      <div className="navbar-inner">
        {showBack ? (
          <button type="button" className="navbar-back" onClick={onBack} aria-label="Go back">
            <span aria-hidden="true">←</span>
          </button>
        ) : (
          <span className="navbar-spacer" aria-hidden="true" />
        )}

        <h1 className="navbar-title">Covrly</h1>
        <button
          type="button"
          className="navbar-profile-btn"
          onClick={onOpenProfileMenu}
          aria-label="Open profile menu"
        >
          {normalizedImage ? (
            <img src={normalizedImage} alt="Profile" className="navbar-profile-image" />
          ) : (
            <span className="navbar-profile-fallback" aria-hidden="true">
              {initials}
            </span>
          )}
        </button>
      </div>
    </header>
  )
}

export default Navbar