const API_BASE = '/api';

export const api = {
  async get(endpoint: string, noCache = false) {
    let url = `${API_BASE}${endpoint}`;
    if (noCache) {
      const sep = endpoint.includes('?') ? '&' : '?';
      url += `${sep}_=${Date.now()}`;
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
    return res.json();
  },
  
  async post(endpoint: string, data: any) {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
        let errStr = res.statusText;
        try {
            const errData = await res.json();
            if (errData.error) errStr = errData.error;
        } catch(e) {}
        throw new Error(errStr);
    }
    return res.json();
  },

  async upload(endpoint: string, formData: FormData) {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error(`Upload Error: ${res.statusText}`);
    return res.json();
  }
};
