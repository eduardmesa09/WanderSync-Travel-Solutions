import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './state/auth'
import { PackageProvider } from './state/package'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <PackageProvider>
          <App />
        </PackageProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
