import { useNavigate } from 'react-router-dom'
import './Settings.css'

const settingItems = [
  { label: 'Edit Profile', route: '/profile' },
  { label: 'Security' },
  { label: 'Notifications' },
  { label: 'Privacy' },
  { label: 'Bank Details' },
  { label: 'Help' },
]

function Settings() {
  const navigate = useNavigate()

  const handleItemClick = (item) => {
    if (item.route) {
      navigate(item.route)
    }
  }

  return (
    <section className="settings-page">
      <header className="settings-header">
        <h1>Settings</h1>
        <p>Manage your account preferences and support options.</p>
      </header>

      <section className="settings-list" aria-label="Settings options">
        {settingItems.map((item) => (
          <button
            key={item.label}
            type="button"
            className="settings-item"
            onClick={() => handleItemClick(item)}
          >
            <span>{item.label}</span>
            <span className="settings-item-arrow" aria-hidden="true">
              &gt;
            </span>
          </button>
        ))}
      </section>
    </section>
  )
}

export default Settings