import { NavLink } from 'react-router-dom'
import './BottomNav.css'

const leftNavItems = [
  { to: '/dashboard', label: 'Home', icon: HomeIcon },
  { to: '/policy', label: 'Policies', icon: PoliciesIcon },
]

const rightNavItems = [
  { to: '/location', label: 'Location', icon: LocationIcon },
  { to: '/profile', label: 'Profile', icon: ProfileIcon },
]

const fabItem = { to: '/claim/manual', label: 'Add', icon: AddIcon }

function BottomNavItem({ item }) {
  const Icon = item.icon

  return (
    <li className="bottom-nav-item">
      <NavLink
        to={item.to}
        className={({ isActive }) =>
          ['bottom-nav-link', isActive ? 'is-active' : ''].filter(Boolean).join(' ')
        }
      >
        <Icon className="bottom-nav-icon" />
        <span className="bottom-nav-label">{item.label}</span>
      </NavLink>
    </li>
  )
}

function BottomNav() {
  const FabIcon = fabItem.icon

  return (
    <nav className="bottom-nav" aria-label="Primary">
      <div className="bottom-nav-inner">
        <ul className="bottom-nav-group bottom-nav-group-left">
          {leftNavItems.map((item) => (
            <BottomNavItem key={item.to} item={item} />
          ))}
        </ul>

        <NavLink
          to={fabItem.to}
          aria-label={fabItem.label}
          className={({ isActive }) =>
            ['bottom-nav-fab', isActive ? 'is-active' : ''].filter(Boolean).join(' ')
          }
        >
          <FabIcon className="bottom-nav-fab-icon" />
        </NavLink>

        <ul className="bottom-nav-group bottom-nav-group-right">
          {rightNavItems.map((item) => (
            <BottomNavItem key={item.to} item={item} />
          ))}
        </ul>
      </div>
    </nav>
  )
}

function HomeIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M3 10.5L12 3l9 7.5M5.25 9.75V20h13.5V9.75"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function PoliciesIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M6 4.5h12A1.5 1.5 0 0119.5 6v12A1.5 1.5 0 0118 19.5H6A1.5 1.5 0 014.5 18V6A1.5 1.5 0 016 4.5zm3 4.5h6m-6 4h6m-6 4h4"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function AddIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 5.25v13.5M5.25 12h13.5"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
    </svg>
  )
}

function LocationIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 21s6-5.32 6-10a6 6 0 10-12 0c0 4.68 6 10 6 10z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M12 13.25a2.25 2.25 0 100-4.5 2.25 2.25 0 000 4.5z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function ProfileIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 12a4.5 4.5 0 100-9 4.5 4.5 0 000 9zm-7.5 8.25a7.5 7.5 0 0115 0"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export default BottomNav