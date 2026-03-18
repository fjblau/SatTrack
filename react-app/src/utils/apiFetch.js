const TOKEN_KEY = 'auth_token'

async function apiFetch(url, options = {}) {
  const token = sessionStorage.getItem(TOKEN_KEY)

  const headers = {
    ...(options.headers || {}),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(url, { ...options, headers })

  if (response.status === 401) {
    sessionStorage.removeItem(TOKEN_KEY)
    window.dispatchEvent(new Event('auth:expired'))
  }

  return response
}

export default apiFetch
