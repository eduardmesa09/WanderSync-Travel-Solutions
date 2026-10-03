import { useEffect } from 'react'
import { Link, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { Footer } from './components/Footer'
import { Header } from './components/Header'
import { RequireAuth } from './components/common'
import { Login, Register } from './pages/Auth'
import BookingDetail from './pages/BookingDetail'
import Checkout from './pages/Checkout'
import Home from './pages/Home'
import MyBookings from './pages/MyBookings'
import Search from './pages/Search'

function Layout() {
  const { pathname, hash } = useLocation()
  const isHome = pathname === '/'

  // Al cambiar de página se vuelve arriba, salvo enlaces a una sección (#destinos).
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'smooth' })
    else window.scrollTo(0, 0)
  }, [pathname, hash])

  return (
    <div className="app">
      <Header overlay={isHome} />
      <main className="app__main">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}

function NotFound() {
  return (
    <div className="container narrow empty section">
      <h1 className="display">404</h1>
      <p>Esta página se perdió en el camino.</p>
      <Link to="/" className="btn btn--pill btn--gold">Volver al inicio</Link>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="buscar" element={<Search />} />
        <Route path="checkout" element={<RequireAuth><Checkout /></RequireAuth>} />
        <Route path="reservas" element={<RequireAuth><MyBookings /></RequireAuth>} />
        <Route path="reservas/:id" element={<RequireAuth><BookingDetail /></RequireAuth>} />
        <Route path="ingresar" element={<Login />} />
        <Route path="registro" element={<Register />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
