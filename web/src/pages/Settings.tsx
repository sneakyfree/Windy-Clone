import { Settings as SettingsIcon, Bell, Shield, Link2, Key, Save, Loader2, Check } from 'lucide-react'
import { useState, useEffect } from 'react'
import { usePreferences, savePreferences } from '../hooks/useClones'

export default function Settings() {
  const { data: prefsData, loading } = usePreferences()

  const [defaultProvider, setDefaultProvider] = useState('elevenlabs')
  const [emailNotifications, setEmailNotifications] = useState(true)
  const [pushNotifications, setPushNotifications] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // Sync from API once loaded
  useEffect(() => {
    if (prefsData?.preferences) {
      setDefaultProvider(prefsData.preferences.default_provider)
      setEmailNotifications(prefsData.preferences.email_notifications)
      setPushNotifications(prefsData.preferences.push_notifications)
    }
  }, [prefsData])

  const handleSave = async () => {
    setSaving(true)
    setSaved(false)
    try {
      await savePreferences({
        default_provider: defaultProvider,
        email_notifications: emailNotifications,
        push_notifications: pushNotifications,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      console.error('Failed to save preferences:', err)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 text-cyan-bright animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-10 max-w-3xl">
      {/* Header */}
      <section className="animate-fade-in-up">
        <div className="flex items-center gap-2 mb-2">
          <SettingsIcon className="w-5 h-5 text-text-muted" />
          <span className="text-sm text-text-muted font-medium tracking-wide uppercase">
            Settings
          </span>
        </div>
        <h1 className="text-3xl md:text-4xl font-display font-bold text-text-primary mb-2">
          Preferences
        </h1>
        <p className="text-base text-text-secondary">
          Customize your Windy Clone experience.
        </p>
      </section>

      {/* Default Provider */}
      <section className="glass-card rounded-2xl p-6 animate-fade-in-up delay-100">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-cyan-glow/15 flex items-center justify-center">
            <Key className="w-5 h-5 text-cyan-bright" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-text-primary">Default Provider</h3>
            <p className="text-sm text-text-muted">Choose your preferred provider for quick actions</p>
          </div>
        </div>
        <select
          id="default-provider"
          value={defaultProvider}
          onChange={(e) => setDefaultProvider(e.target.value)}
          className="w-full h-11 px-4 rounded-xl bg-windy-card border border-windy-border text-text-primary text-sm focus:outline-none focus:border-cyan-glow/40 appearance-none cursor-pointer"
        >
          <option value="elevenlabs">ElevenLabs (Voice Twin)</option>
          <option value="heygen">HeyGen (Digital Avatar)</option>
          <option value="playht">PlayHT (Voice Twin)</option>
          <option value="resembleai">Resemble AI (Voice Twin)</option>
        </select>
      </section>

      {/* Notifications */}
      <section className="glass-card rounded-2xl p-6 animate-fade-in-up delay-200">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-purple-glow/15 flex items-center justify-center">
            <Bell className="w-5 h-5 text-purple-bright" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-text-primary">Notifications</h3>
            <p className="text-sm text-text-muted">Get notified when your clone is ready</p>
          </div>
        </div>
        <div className="space-y-4">
          <label className="flex items-center justify-between cursor-pointer">
            <span className="text-sm text-text-secondary">Email notifications</span>
            <button
              onClick={() => setEmailNotifications(!emailNotifications)}
              className={`w-11 h-6 rounded-full transition-all duration-200 ${
                emailNotifications ? 'bg-cyan-glow' : 'bg-windy-border'
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full bg-white shadow-sm transform transition-transform duration-200 ${
                  emailNotifications ? 'translate-x-[22px]' : 'translate-x-[2px]'
                }`}
              />
            </button>
          </label>
          <label className="flex items-center justify-between cursor-pointer">
            <span className="text-sm text-text-secondary">Push notifications</span>
            <button
              onClick={() => setPushNotifications(!pushNotifications)}
              className={`w-11 h-6 rounded-full transition-all duration-200 ${
                pushNotifications ? 'bg-cyan-glow' : 'bg-windy-border'
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full bg-white shadow-sm transform transition-transform duration-200 ${
                  pushNotifications ? 'translate-x-[22px]' : 'translate-x-[2px]'
                }`}
              />
            </button>
          </label>
        </div>
      </section>

      {/* Privacy */}
      <section className="glass-card rounded-2xl p-6 animate-fade-in-up delay-300">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-emerald-glow/15 flex items-center justify-center">
            <Shield className="w-5 h-5 text-emerald-glow" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-text-primary">Privacy & Data</h3>
            <p className="text-sm text-text-muted">Control how your data is used</p>
          </div>
        </div>
        <p className="text-sm text-text-secondary leading-relaxed">
          Your recordings stay in the Windy ecosystem until you choose to send them to a provider. 
          You can download or delete all your data at any time from the My Clones page.
        </p>
      </section>

      {/* Connected Accounts */}
      <section className="glass-card rounded-2xl p-6 animate-fade-in-up delay-400">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-amber-glow/15 flex items-center justify-center">
            <Link2 className="w-5 h-5 text-amber-glow" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-text-primary">Connected Accounts</h3>
            <p className="text-sm text-text-muted">Windy products feeding your legacy data</p>
          </div>
        </div>
        <div className="space-y-3">
          <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-windy-card border border-windy-border">
            <span className="text-sm text-text-primary">Windy Pro Desktop</span>
            <span className="text-xs text-emerald-glow font-medium">Connected</span>
          </div>
          <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-windy-card border border-windy-border">
            <span className="text-sm text-text-primary">Windy Pro Mobile</span>
            <span className="text-xs text-emerald-glow font-medium">Connected</span>
          </div>
          <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-windy-card border border-windy-border">
            <span className="text-sm text-text-primary">Windy Cloud</span>
            <span className="text-xs text-text-muted font-medium">Not Connected</span>
          </div>
        </div>
      </section>

      {/* Save button */}
      <div className="animate-fade-in-up delay-500">
        <button
          id="save-settings"
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-glow to-cyan-bright text-windy-dark font-semibold text-sm hover:shadow-[0_0_25px_rgba(6,182,212,0.3)] transition-all duration-200 active:scale-[0.98] disabled:opacity-60"
        >
          {saving ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : saved ? (
            <Check className="w-4 h-4" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Preferences'}
        </button>
      </div>
    </div>
  )
}
