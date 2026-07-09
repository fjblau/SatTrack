import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import NextPassPage from './components/NextPassPage'
import './index.css'

const isNextPassRoute = window.location.pathname === '/next-pass'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {isNextPassRoute ? <NextPassPage /> : <App />}
  </React.StrictMode>,
)
