const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

export const api = {
  confirmJob: async (jobData: any) => {
    const response = await fetch(`${API_BASE_URL}/jobs/confirm_job/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // Add auth headers if needed
        // 'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(jobData),
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  },
  
  // Add other API methods here...
};