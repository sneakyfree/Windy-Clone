import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Legacy from './pages/Legacy'
import Discover from './pages/Discover'
import Studio from './pages/Studio'
import ProviderDetail from './pages/ProviderDetail'
import MyClones from './pages/MyClones'
import Settings from './pages/Settings'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/legacy" replace />} />
        <Route path="/legacy" element={<Legacy />} />
        <Route path="/discover" element={<Discover />} />
        <Route path="/studio" element={<Studio />} />
        <Route path="/studio/:providerId" element={<ProviderDetail />} />
        <Route path="/my-clones" element={<MyClones />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
