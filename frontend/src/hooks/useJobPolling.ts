import { useState, useEffect } from 'react';
import { api } from '../api';

export function useJobPolling() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    if (!jobId) return;
    
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/jobs/status/${jobId}`);
        setStatus(res);
        if (!res.running) {
          clearInterval(interval);
        }
      } catch(e) {
        setStatus({ running: false, error: 'Mất kết nối tới server' });
        clearInterval(interval);
      }
    }, 2000);
    
    return () => clearInterval(interval);
  }, [jobId]);

  const startJob = (id: string) => {
    setJobId(id);
    setStatus({ running: true, progress: 10, message: 'Đang khởi tạo...' });
  };
  
  const resetJob = () => {
    setJobId(null);
    setStatus(null);
  };

  return { jobId, status, startJob, resetJob };
}
