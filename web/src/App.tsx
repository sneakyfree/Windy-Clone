import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import DeepLinkGateway from './components/DeepLinkGateway'
import Legacy from './pages/Legacy'
import Discover from './pages/Discover'
import Studio from './pages/Studio'
import ProviderDetail from './pages/ProviderDetail'
import MyClones from './pages/MyClones'
import Settings from './pages/Settings'

/**
 * Preserve the `search` string when redirecting `/` → `/legacy`.
 *
 * Fixes H-1 in `docs/HARDENING_REPORT.md`: a bare `<Navigate to="/legacy" />`
 * drops the source location's query, so `/?wc=windyclone://discover` landed
 * on `/legacy` with no `?wc=` for `<DeepLinkGateway />` to pick up. The
 * gateway's `useEffect` runs after render, by which time the redirect has
 * already happened. Forwarding `search` keeps the query alive through the
 * redirect so the gateway sees it at `/legacy?wc=...` and navigates onward.
 */
function RootRedirect() {
  const { search } = useLocation()
  return <Navigate to={{ pathname: '/legacy', search }} replace />
}

export default function App() {
  return (
    <>
      <DeepLinkGateway />
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/legacy" element={<Legacy />} />
          <Route path="/discover" element={<Discover />} />
          <Route path="/studio" element={<Studio />} />
          <Route path="/studio/:providerId" element={<ProviderDetail />} />
          <Route path="/studio/clone/:cloneId" element={<MyClones />} />
          <Route path="/order/:orderId" element={<MyClones />} />
          <Route path="/my-clones" element={<MyClones />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </>
  )
}
